"""Connections to providers (FR-010 to FR-013).

The code host is connected by authorization: the person installs the Pono app on their account and
Pono links that installation, with no key to paste. Hosting and database providers without an
authorization flow take a key, stored encrypted and traced on every use (D-007).
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.ports import (
    CodeHost,
    KeyUseLog,
    ProviderAuthorizationError,
    ProviderFactory,
    ProviderUnavailableError,
    StoredConnection,
)
from pono_api.domain.projects import ConnectionKind, ConnectionStatus
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.connections")

CODE_HOST_PROVIDER = "github"
_SELECT = (
    "SELECT id, kind, provider, external_ref, endpoint, secret_ciphertext, status, "
    "status_checked_at FROM connections"
)
_RETURNING = (
    " RETURNING id, kind, provider, external_ref, endpoint, secret_ciphertext, status, "
    "status_checked_at"
)


@dataclass(frozen=True, slots=True)
class ConnectionView:
    id: UUID
    kind: ConnectionKind
    provider: str
    external_ref: str
    status: ConnectionStatus
    status_checked_at: datetime

    def to_payload(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "provider": self.provider,
            "externalRef": self.external_ref,
            "status": self.status.value,
            "statusCheckedAt": self.status_checked_at.isoformat(),
        }


def _view(row: Row[Any]) -> ConnectionView:
    return ConnectionView(
        id=row.id,
        kind=ConnectionKind(row.kind),
        provider=row.provider,
        external_ref=row.external_ref,
        status=ConnectionStatus(row.status),
        status_checked_at=row.status_checked_at,
    )


def stored(row: Row[Any]) -> StoredConnection:
    return StoredConnection(
        id=row.id,
        kind=ConnectionKind(row.kind),
        provider=row.provider,
        external_ref=row.external_ref,
        endpoint=row.endpoint,
        secret_ciphertext=row.secret_ciphertext,
        status=row.status,
    )


async def load_connections(session: AsyncSession) -> list[StoredConnection]:
    query = _SELECT + " ORDER BY created_at"
    rows = await session.execute(text(query))
    return [stored(row) for row in rows]


async def list_connections(
    sessions: async_sessionmaker[AsyncSession], principal: Principal
) -> list[ConnectionView]:
    async with unit_of_work(sessions, principal) as session:
        rows = await session.execute(text(_SELECT + " ORDER BY kind, created_at"))
        return [_view(row) for row in rows]


async def active_code_host(session: AsyncSession) -> StoredConnection | None:
    row = (
        await session.execute(
            text(
                _SELECT
                + " WHERE kind = 'code_host' AND status = 'active' ORDER BY created_at LIMIT 1"
            )
        )
    ).first()
    return stored(row) if row else None


async def link_code_host(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, code_host: CodeHost
) -> ConnectionView:
    """Link the installation the person made on their own account (FR-010)."""

    async with unit_of_work(sessions, principal) as session:
        account_id = (
            await session.execute(
                text("SELECT code_host_user_id FROM people WHERE id = :id"),
                {"id": principal.person_id},
            )
        ).scalar_one()
    try:
        installation_id = await code_host.find_installation(account_id)
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    if installation_id is None:
        raise ApiError("connection.code_host_not_installed", 422)

    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text(
                    "INSERT INTO connections (id, organization_id, kind, provider, external_ref) "
                    "VALUES (:id, :organization_id, 'code_host', :provider, :external_ref) "
                    "ON CONFLICT (organization_id, provider, external_ref) DO UPDATE "
                    "SET status = 'active', status_checked_at = now()" + _RETURNING
                ),
                {
                    "id": uuid7(),
                    "organization_id": principal.organization_id,
                    "provider": CODE_HOST_PROVIDER,
                    "external_ref": installation_id,
                },
            )
        ).one()
    return _view(row)


async def register_connection(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    factory: ProviderFactory,
    *,
    kind: ConnectionKind,
    provider: str,
    authorization: str,
    endpoint: str | None,
) -> ConnectionView:
    """Check a provider key, then store it encrypted (FR-011). The key is never returned."""

    if kind is ConnectionKind.CODE_HOST or not factory.supports(kind, provider):
        raise ApiError("connection.provider_unsupported", 422, "provider")
    uses: list[str] = []
    try:
        adapter = (
            factory.probe_hosting(provider, authorization, endpoint)
            if kind is ConnectionKind.HOSTING
            else factory.probe_database(provider, authorization, endpoint)
        )
        external_ref = await adapter.verify()
        uses.append("verify")
    except ProviderAuthorizationError as error:
        raise ApiError("connection.authorization_invalid", 422, "authorization") from error
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    except ValueError as error:
        raise ApiError("connection.provider_unsupported", 422, "endpoint") from error

    sealed = factory.seal(authorization)
    try:
        async with unit_of_work(sessions, principal) as session:
            row = (
                await session.execute(
                    text(
                        "INSERT INTO connections (id, organization_id, kind, provider, "
                        "external_ref, endpoint, secret_ciphertext) "
                        "VALUES (:id, :organization_id, :kind, :provider, :external_ref, "
                        ":endpoint, :secret) "
                        # A revoked connection may be authorized again with a new key.
                        "ON CONFLICT (organization_id, provider, external_ref) DO UPDATE "
                        "SET secret_ciphertext = EXCLUDED.secret_ciphertext, "
                        "endpoint = EXCLUDED.endpoint, status = 'active', "
                        "status_checked_at = now() WHERE connections.status <> 'active'"
                        + _RETURNING
                    ),
                    {
                        "id": uuid7(),
                        "organization_id": principal.organization_id,
                        "kind": kind.value,
                        "provider": provider,
                        "external_ref": external_ref,
                        "endpoint": endpoint,
                        "secret": sealed,
                    },
                )
            ).first()
            if row is None:
                raise ApiError("connection.duplicate", 409)
            log = KeyUseLog()
            for action in uses:
                log.recorder(row.id)(action)
            await record_key_uses(session, principal.organization_id, log)
    except IntegrityError as error:
        raise ApiError("connection.duplicate", 409) from error
    return _view(row)


async def revoke_connection(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    code_host: CodeHost | None,
    connection_id: UUID,
) -> None:
    """Revoke with immediate effect (FR-012): the key is erased, the installation removed."""

    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text(_SELECT + " WHERE id = :id"),
                {"id": connection_id},
            )
        ).first()
    if row is None:
        raise not_found("connection")
    connection = stored(row)
    if connection.kind is ConnectionKind.CODE_HOST and code_host is not None:
        try:
            await code_host.revoke_installation(connection.external_ref)
        except ProviderUnavailableError as error:
            raise ApiError("provider.unavailable", 503) from error
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE connections SET status = 'revoked', secret_ciphertext = NULL, "
                "status_checked_at = now() WHERE id = :id"
            ),
            {"id": connection_id},
        )


async def refresh_connection_statuses(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    code_host: CodeHost | None,
    factory: ProviderFactory,
) -> None:
    """Re-check every connection that is not revoked (FR-013). Revocation is final."""

    async with unit_of_work(sessions, principal) as session:
        connections = [
            connection
            for connection in await load_connections(session)
            if connection.status != ConnectionStatus.REVOKED.value
        ]
    log = KeyUseLog()
    statuses: dict[UUID, ConnectionStatus] = {}
    for connection in connections:
        try:
            statuses[connection.id] = await _check(connection, code_host, factory, log)
        except ProviderUnavailableError:
            logger.warning("connection %s could not be checked; status kept", connection.id)
    async with unit_of_work(sessions, principal) as session:
        for connection_id, status in statuses.items():
            await session.execute(
                text(
                    "UPDATE connections SET status = :status, status_checked_at = now() "
                    "WHERE id = :id"
                ),
                {"id": connection_id, "status": status.value},
            )
        await record_key_uses(session, principal.organization_id, log)


async def _check(
    connection: StoredConnection,
    code_host: CodeHost | None,
    factory: ProviderFactory,
    log: KeyUseLog,
) -> ConnectionStatus:
    if connection.kind is ConnectionKind.CODE_HOST:
        if code_host is None:
            raise ProviderUnavailableError("code host is not configured")
        active = await code_host.installation_active(connection.external_ref)
        return ConnectionStatus.ACTIVE if active else ConnectionStatus.REVOKED
    try:
        record = log.recorder(connection.id)
        adapter = (
            factory.hosting(connection, record)
            if connection.kind is ConnectionKind.HOSTING
            else factory.database(connection, record)
        )
        await adapter.verify()
    except ProviderAuthorizationError:
        return ConnectionStatus.EXPIRED
    return ConnectionStatus.ACTIVE


__all__ = [
    "CODE_HOST_PROVIDER",
    "ConnectionView",
    "active_code_host",
    "link_code_host",
    "list_connections",
    "load_connections",
    "refresh_connection_statuses",
    "register_connection",
    "revoke_connection",
    "stored",
]
