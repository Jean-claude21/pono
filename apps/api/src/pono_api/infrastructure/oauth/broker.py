"""OAuth 2.1 authorization server for agents, ported from KYA-Platform's broker (003 research R-02).

It implements the MCP SDK's provider: dynamic client registration, authorization with PKCE,
consent in the console, code exchange, refresh with rotation, revocation. Everything before a person
is known goes through the SECURITY DEFINER functions of migration 0006; tokens and codes are opaque
and only their SHA-256 digests are stored.
"""

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID, uuid7

from cryptography.fernet import Fernet, InvalidToken
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    IdentityAssertionParams,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import SecretStr
from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.domain.agents import (
    ACCESS_TOKEN_LIFETIME,
    ALL_SCOPES,
    AUTHORIZATION_CODE_LIFETIME,
    CONSENT_REQUEST_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
)
from pono_api.infrastructure.database.rls import Principal, unit_of_work


def digest(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


def _opaque() -> str:
    return secrets.token_urlsafe(32)


class AgentCode(AuthorizationCode):
    grant_id: UUID


class AgentRefreshToken(RefreshToken):
    grant_id: UUID


class AgentAccessToken(AccessToken):
    """What the tools server knows about the caller, and nothing more (no token, no secret)."""

    grant_id: UUID
    organization_id: UUID
    person_id: UUID
    client_name: str

    @property
    def principal(self) -> Principal:
        return Principal(person_id=self.person_id, organization_ids=(self.organization_id,))


class AgentBroker:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        issuer_url: str,
        resource_url: str,
        consent_url: str,
        secret_key: SecretStr,
    ) -> None:
        self._sessions = sessions
        self._issuer_url = issuer_url.rstrip("/")
        self._resource_url = resource_url.rstrip("/")
        self._consent_url = consent_url
        self._cipher = Fernet(secret_key.get_secret_value().encode())

    @property
    def resource_url(self) -> str:
        return self._resource_url

    async def _call(self, statement: str, parameters: dict[str, object]) -> list[Row[Any]]:
        async with unit_of_work(self._sessions, None) as session:
            return list(await session.execute(text(statement), parameters))

    # --- clients --------------------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        rows = await self._call(
            "SELECT metadata, secret_ciphertext FROM pono_agent_client(:client_id)",
            {"client_id": client_id},
        )
        if not rows:
            return None
        row = rows[0]
        metadata = dict(row.metadata)
        metadata["client_id"] = client_id
        secret = row.secret_ciphertext
        if secret is not None:
            try:
                metadata["client_secret"] = self._cipher.decrypt(bytes(secret)).decode()
            except InvalidToken:
                return None
        return OAuthClientInformationFull.model_validate(metadata)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            raise RegistrationError("invalid_client_metadata", "Missing client id")
        scopes = set((client_info.scope or "").split())
        if not scopes.issubset(ALL_SCOPES):
            raise RegistrationError("invalid_client_metadata", "Unsupported scope")
        metadata = client_info.model_dump(mode="json", exclude={"client_id", "client_secret"})
        secret = (
            self._cipher.encrypt(client_info.client_secret.encode())
            if client_info.client_secret
            else None
        )
        await self._call(
            "SELECT pono_agent_register(:client_id, CAST(:metadata AS jsonb), :secret)",
            {
                "client_id": client_info.client_id,
                "metadata": json.dumps(metadata),
                "secret": secret,
            },
        )

    # --- authorization and consent --------------------------------------------------------------

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        if params.resource is not None and params.resource.rstrip("/") != self._resource_url:
            raise AuthorizeError("invalid_request", "Unknown resource")
        scopes = tuple(params.scopes or ALL_SCOPES)
        if not set(scopes).issubset(ALL_SCOPES):
            raise AuthorizeError("invalid_scope", "Unsupported scope")
        handle = _opaque()
        await self._call(
            "SELECT pono_agent_open_request(:id, :digest, :client_id, :redirect_uri, :explicit, "
            ":challenge, :scopes, :state, :resource, :expires)",
            {
                "id": uuid7(),
                "digest": digest(handle),
                "client_id": client.client_id,
                "redirect_uri": str(params.redirect_uri),
                "explicit": params.redirect_uri_provided_explicitly,
                "challenge": params.code_challenge,
                "scopes": list(scopes),
                "state": params.state,
                "resource": self._resource_url,
                "expires": datetime.now(UTC) + CONSENT_REQUEST_LIFETIME,
            },
        )
        return f"{self._consent_url}?{urlencode({'request': handle})}"

    async def consent_request(self, handle: str) -> tuple[str, tuple[str, ...], datetime] | None:
        rows = await self._call(
            "SELECT client_name, scopes, expires_at FROM pono_agent_request(:digest)",
            {"digest": digest(handle)},
        )
        if not rows:
            return None
        row = rows[0]
        return row.client_name, tuple(row.scopes), row.expires_at

    async def decide(
        self, principal: Principal, handle: str, *, scopes: tuple[str, ...] | None
    ) -> str | None:
        """The person's decision, taken in their own session; `None` scopes means a refusal."""

        code = _opaque()
        async with unit_of_work(self._sessions, principal) as session:
            row = (
                await session.execute(
                    text(
                        "SELECT redirect_uri, state FROM pono_agent_decide(:digest, :approve, "
                        ":code, :scopes, :grant_id, :expires)"
                    ),
                    {
                        "digest": digest(handle),
                        "approve": scopes is not None,
                        "code": digest(code),
                        "scopes": list(scopes or ()),
                        "grant_id": uuid7(),
                        "expires": datetime.now(UTC) + AUTHORIZATION_CODE_LIFETIME,
                    },
                )
            ).first()
        if row is None:
            return None
        if scopes is None:
            return construct_redirect_uri(
                row.redirect_uri, error="access_denied", state=row.state, iss=self._issuer_url
            )
        return construct_redirect_uri(
            row.redirect_uri, code=code, state=row.state, iss=self._issuer_url
        )

    # --- tokens ---------------------------------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AgentCode | None:
        rows = await self._call(
            "SELECT grant_id, scopes, code_challenge, redirect_uri, redirect_uri_explicit, "
            "resource, expires_at, person_id FROM pono_agent_code(:digest, :client_id)",
            {"digest": digest(authorization_code), "client_id": client.client_id},
        )
        if not rows:
            return None
        row = rows[0]
        return AgentCode(
            code=authorization_code,
            scopes=list(row.scopes),
            expires_at=row.expires_at.timestamp(),
            client_id=str(client.client_id),
            code_challenge=row.code_challenge,
            redirect_uri=row.redirect_uri,
            redirect_uri_provided_explicitly=row.redirect_uri_explicit,
            resource=row.resource,
            subject=str(row.person_id),
            grant_id=row.grant_id,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if not isinstance(authorization_code, AgentCode):
            raise TokenError("invalid_grant", "Unknown authorization code")
        access, refresh = _opaque(), _opaque()
        now = datetime.now(UTC)
        rows = await self._call(
            "SELECT pono_agent_issue(:code, :client_id, :access, :refresh, :access_expires, "
            ":refresh_expires) AS issued",
            {
                "code": digest(authorization_code.code),
                "client_id": client.client_id,
                "access": digest(access),
                "refresh": digest(refresh),
                "access_expires": now + ACCESS_TOKEN_LIFETIME,
                "refresh_expires": now + REFRESH_TOKEN_LIFETIME,
            },
        )
        if not rows or not rows[0].issued:
            raise TokenError("invalid_grant", "Authorization code already used")
        return self._token(access, refresh, authorization_code.scopes)

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> AgentRefreshToken | None:
        row = await self._token_row(refresh_token, "refresh")
        if row is None or row.client_id != client.client_id:
            return None
        return AgentRefreshToken(
            token=refresh_token,
            client_id=row.client_id,
            scopes=list(row.scopes),
            expires_at=int(row.expires_at.timestamp()),
            subject=str(row.person_id),
            grant_id=row.grant_id,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if not isinstance(refresh_token, AgentRefreshToken):
            raise TokenError("invalid_grant", "Unknown refresh token")
        if not set(scopes).issubset(refresh_token.scopes):
            raise TokenError("invalid_scope", "Scopes cannot grow on refresh")
        access, refresh = _opaque(), _opaque()
        now = datetime.now(UTC)
        rows = await self._call(
            "SELECT pono_agent_rotate(:old, :client_id, :access, :refresh, :access_expires, "
            ":refresh_expires) AS rotated",
            {
                "old": digest(refresh_token.token),
                "client_id": client.client_id,
                "access": digest(access),
                "refresh": digest(refresh),
                "access_expires": now + ACCESS_TOKEN_LIFETIME,
                "refresh_expires": now + REFRESH_TOKEN_LIFETIME,
            },
        )
        if not rows or not rows[0].rotated:
            raise TokenError("invalid_grant", "Refresh token already used or revoked")
        return self._token(access, refresh, refresh_token.scopes)

    async def load_access_token(self, token: str) -> AgentAccessToken | None:
        row = await self._token_row(token, "access")
        if row is None:
            return None
        await self._call("SELECT pono_agent_touch(:grant_id)", {"grant_id": row.grant_id})
        return AgentAccessToken(
            token=token,
            client_id=row.client_id,
            scopes=list(row.scopes),
            expires_at=int(row.expires_at.timestamp()),
            resource=self._resource_url,
            subject=str(row.person_id),
            grant_id=row.grant_id,
            organization_id=row.organization_id,
            person_id=row.person_id,
            client_name=row.client_name,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        await self._call("SELECT pono_agent_revoke(:digest)", {"digest": digest(token.token)})

    async def exchange_identity_assertion(
        self, client: OAuthClientInformationFull, params: IdentityAssertionParams
    ) -> OAuthToken:
        del client, params
        raise TokenError("unsupported_grant_type", "Identity assertion is not enabled")

    async def _token_row(self, token: str, kind: str) -> Row[Any] | None:
        rows = await self._call(
            "SELECT grant_id, organization_id, person_id, client_id, client_name, scopes, "
            "expires_at FROM pono_agent_token(:digest, :kind)",
            {"digest": digest(token), "kind": kind},
        )
        return rows[0] if rows else None

    @staticmethod
    def _token(access: str, refresh: str, scopes: list[str]) -> OAuthToken:
        return OAuthToken(
            access_token=access,
            expires_in=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
            scope=" ".join(scopes),
            refresh_token=refresh,
        )


__all__ = ["AgentAccessToken", "AgentBroker", "digest"]
