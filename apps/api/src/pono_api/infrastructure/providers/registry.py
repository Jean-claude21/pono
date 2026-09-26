"""Builds provider adapters from stored connections. The only place that decrypts a key."""

import httpx
from pydantic import SecretStr

from pono_api.application.ports import (
    DatabaseProvider,
    HostingProvider,
    KeyUse,
    ProviderAuthorizationError,
    RuntimeHost,
    StoredConnection,
)
from pono_api.domain.projects import ConnectionKind
from pono_api.infrastructure.crypto import CredentialCipher, CredentialCipherError
from pono_api.infrastructure.providers.coolify import CoolifyHosting
from pono_api.infrastructure.providers.neon import NeonDatabase
from pono_api.infrastructure.providers.netlify import NetlifyHosting

SUPPORTED: dict[ConnectionKind, frozenset[str]] = {
    ConnectionKind.CODE_HOST: frozenset({"github"}),
    ConnectionKind.HOSTING: frozenset({"netlify", "coolify"}),
    ConnectionKind.DATABASE: frozenset({"neon"}),
}
NEEDS_ENDPOINT = frozenset({"coolify"})


class UnsupportedProviderError(ValueError):
    """No adapter exists for this provider, or it lacks a required setting."""


class ProviderRegistry:
    def __init__(
        self, cipher: CredentialCipher | None, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._cipher = cipher
        self._transport = transport

    def supports(self, kind: ConnectionKind, provider: str) -> bool:
        return provider in SUPPORTED.get(kind, frozenset())

    def seal(self, authorization: str) -> bytes:
        return self._require_cipher().encrypt(SecretStr(authorization))

    def hosting(self, connection: StoredConnection, on_use: KeyUse) -> HostingProvider:
        return self.probe_hosting(
            connection.provider, self._open(connection), connection.endpoint, on_use
        )

    def database(self, connection: StoredConnection, on_use: KeyUse) -> DatabaseProvider:
        return self.probe_database(
            connection.provider, self._open(connection), connection.endpoint, on_use
        )

    def runtime_host(self, connection: StoredConnection, on_use: KeyUse) -> RuntimeHost | None:
        """Only a server of one's own runs a development runtime (004, D-009)."""

        if connection.provider != "coolify" or not connection.endpoint:
            return None
        return CoolifyHosting(
            connection.endpoint, self._open(connection), on_use, transport=self._transport
        )

    def probe_hosting(
        self,
        provider: str,
        authorization: str,
        endpoint: str | None,
        on_use: KeyUse | None = None,
    ) -> HostingProvider:
        record = on_use or _ignore
        if provider == "netlify":
            return NetlifyHosting(authorization, record, transport=self._transport)
        if provider == "coolify":
            if not endpoint:
                raise UnsupportedProviderError("coolify needs its endpoint")
            return CoolifyHosting(endpoint, authorization, record, transport=self._transport)
        raise UnsupportedProviderError(provider)

    def probe_database(
        self,
        provider: str,
        authorization: str,
        endpoint: str | None,
        on_use: KeyUse | None = None,
    ) -> DatabaseProvider:
        del endpoint
        if provider == "neon":
            return NeonDatabase(authorization, on_use or _ignore, transport=self._transport)
        raise UnsupportedProviderError(provider)

    def _open(self, connection: StoredConnection) -> str:
        if connection.secret_ciphertext is None:
            raise ProviderAuthorizationError("connection holds no credential")
        try:
            return self._require_cipher().decrypt(connection.secret_ciphertext).get_secret_value()
        except CredentialCipherError as error:
            raise ProviderAuthorizationError("stored credential cannot be opened") from error

    def _require_cipher(self) -> CredentialCipher:
        if self._cipher is None:
            raise UnsupportedProviderError("encryption key is not configured")
        return self._cipher


def _ignore(_: str) -> None:
    return None


__all__ = ["NEEDS_ENDPOINT", "SUPPORTED", "ProviderRegistry", "UnsupportedProviderError"]
