"""Quota readings and alerts (FR-024, FR-025, SC-004).

Readings are taken per organization: the account quotas of each hosting connection, and the
quotas of each project's database. An alert is inserted once per resource, metric, threshold and
billing period; the database's unique key makes a second insert a no-op, so the email is sent once.
"""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import load_connections
from pono_api.application.ports import (
    KeyUseLog,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RaisedAlert,
    Recipient,
    StoredConnection,
)
from pono_api.application.refresh_project import Providers
from pono_api.domain.manifest import ProjectManifest
from pono_api.domain.projects import ConnectionKind
from pono_api.domain.quotas import QuotaReading, crossed_thresholds
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.quotas")


@dataclass(frozen=True, slots=True)
class Taken:
    connection_id: UUID
    project_id: UUID | None
    project_name: str | None
    reading: QuotaReading


async def read_quotas(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, providers: Providers
) -> int:
    """Take every quota reading of the organization; returns how many alerts were raised."""

    async with unit_of_work(sessions, principal) as session:
        connections = await load_connections(session)
        projects = list(await session.execute(text("SELECT id, name, manifest FROM projects")))

    log = KeyUseLog()
    taken = await _hosting(connections, providers, log) + await _databases(
        connections, projects, providers, log
    )
    async with unit_of_work(sessions, principal) as session:
        for item in taken:
            await _store(session, principal.organization_id, item)
        raised = [
            alert
            for item in taken
            for alert in await _raise(session, principal.organization_id, item)
        ]
        await record_key_uses(session, principal.organization_id, log)
    if raised:
        await _email(sessions, principal, providers, raised)
    return len(raised)


def _active(connections: list[StoredConnection], kind: ConnectionKind) -> list[StoredConnection]:
    return [c for c in connections if c.kind is kind and c.status == "active"]


async def _hosting(
    connections: list[StoredConnection], providers: Providers, log: KeyUseLog
) -> list[Taken]:
    taken: list[Taken] = []
    for connection in _active(connections, ConnectionKind.HOSTING):
        try:
            readings = await providers.factory.hosting(
                connection, log.recorder(connection.id)
            ).read_quotas()
        except ProviderUnavailableError, ProviderAuthorizationError:
            logger.warning("quotas of connection %s could not be read", connection.id)
            continue
        taken.extend(Taken(connection.id, None, None, reading) for reading in readings)
    return taken


async def _databases(
    connections: list[StoredConnection],
    projects: list[Row[Any]],
    providers: Providers,
    log: KeyUseLog,
) -> list[Taken]:
    taken: list[Taken] = []
    databases = _active(connections, ConnectionKind.DATABASE)
    for project in projects:
        database = ProjectManifest.model_validate(project.manifest).database
        if database is None:
            continue
        connection = next((c for c in databases if c.provider == database.provider), None)
        if connection is None:
            continue
        try:
            readings = await providers.factory.database(
                connection, log.recorder(connection.id)
            ).read_quotas(database.ref)
        except ProviderUnavailableError, ProviderAuthorizationError:
            logger.warning("quotas of project %s could not be read", project.id)
            continue
        taken.extend(Taken(connection.id, project.id, project.name, r) for r in readings)
    return taken


# ON CONFLICT repeats the unique indexes' expressions literally, or Postgres cannot match them.
async def _store(session: AsyncSession, organization_id: UUID, item: Taken) -> None:
    reading = item.reading
    await session.execute(
        text(
            "INSERT INTO quota_readings (id, organization_id, project_id, connection_id, metric, "
            'used, "limit", limit_source, period_start, period_end) '
            "VALUES (:id, :organization_id, :project_id, :connection_id, :metric, :used, :limit, "
            ":source, :start, :end) "
            "ON CONFLICT (connection_id, "
            "COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid), metric, "
            'period_start) DO UPDATE SET used = EXCLUDED.used, "limit" = EXCLUDED."limit", '
            "limit_source = EXCLUDED.limit_source, period_end = EXCLUDED.period_end, "
            "read_at = now()"
        ),
        {
            "id": uuid7(),
            "organization_id": organization_id,
            "project_id": item.project_id,
            "connection_id": item.connection_id,
            "metric": reading.metric.value,
            "used": reading.used,
            "limit": reading.limit,
            "source": reading.limit_source.value,
            "start": reading.period_start,
            "end": reading.period_end,
        },
    )


async def _raise(
    session: AsyncSession, organization_id: UUID, item: Taken
) -> list[tuple[UUID, RaisedAlert]]:
    reading = item.reading
    raised: list[tuple[UUID, RaisedAlert]] = []
    for threshold in crossed_thresholds(reading.ratio):
        inserted = (
            await session.execute(
                text(
                    "INSERT INTO alerts (id, organization_id, project_id, connection_id, metric, "
                    "threshold, ratio, period_start) VALUES (:id, :organization_id, :project_id, "
                    ":connection_id, :metric, :threshold, :ratio, :start) "
                    "ON CONFLICT (organization_id, connection_id, "
                    "COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid), "
                    "metric, threshold, period_start) "
                    "DO NOTHING RETURNING id"
                ),
                {
                    "id": uuid7(),
                    "organization_id": organization_id,
                    "project_id": item.project_id,
                    "connection_id": item.connection_id,
                    "metric": reading.metric.value,
                    "threshold": threshold,
                    "ratio": reading.ratio,
                    "start": reading.period_start,
                },
            )
        ).first()
        if inserted is not None and reading.limit is not None:
            raised.append(
                (
                    inserted.id,
                    RaisedAlert(
                        project_name=item.project_name,
                        metric=reading.metric.value,
                        threshold=threshold,
                        used=reading.used,
                        limit=reading.limit,
                        limit_source=reading.limit_source.value,
                    ),
                )
            )
    return raised


async def _email(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    raised: list[tuple[UUID, RaisedAlert]],
) -> None:
    mailer = providers.mailer
    if mailer is None or not mailer.configured:
        return
    async with unit_of_work(sessions, principal) as session:
        recipients = [
            Recipient(email=row.email, locale=row.locale)
            for row in await session.execute(
                text("SELECT email, locale FROM pono_alert_recipients(:organization_id)"),
                {"organization_id": principal.organization_id},
            )
        ]
    sent: list[UUID] = []
    for alert_id, alert in raised:
        try:
            for recipient in recipients:
                await mailer.send_alert(recipient, alert)
        except Exception:  # an unreachable mail server never loses the alert itself
            logger.exception("alert email could not be sent")
            continue
        sent.append(alert_id)
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text("UPDATE alerts SET emailed_at = now() WHERE id = ANY(:ids)"), {"ids": sent}
        )


__all__ = ["read_quotas"]
