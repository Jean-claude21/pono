"""Client of a runtime's gate (004 contracts/runtime-gate.md).

The token shared with the gate is sealed at rest with the service's key and unsealed only here, to
sign a ticket or call the gate. The deploy key pair is generated here; its private half goes to the
runtime's host and is never kept.
"""

import base64
import secrets
from datetime import datetime
from typing import cast
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import SecretStr

from pono_api.application.ports import (
    GateRefusedError,
    GateStatus,
    RuntimeCredentials,
    RuntimeUnreachableError,
)
from pono_api.domain.runtimes import RuntimeTicket
from pono_api.infrastructure.crypto import CredentialCipher

JsonObject = dict[str, object]


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class HttpRuntimeGate:
    def __init__(
        self,
        cipher: CredentialCipher,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10,
    ) -> None:
        self._cipher = cipher
        self._transport = transport
        self._timeout = timeout

    def new_credentials(self) -> RuntimeCredentials:
        token = secrets.token_urlsafe(32)
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        ).decode()
        public = (
            key.public_key()
            .public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
            .decode()
        )
        return RuntimeCredentials(
            token=token,
            sealed_token=self._cipher.encrypt(SecretStr(token)),
            private_key=private,
            public_key=public,
        )

    def ticket(self, sealed_token: bytes, runtime_id: UUID) -> str:
        token = self._cipher.decrypt(sealed_token).get_secret_value()
        return RuntimeTicket.issue(runtime_id).sign(token)

    async def status(self, url: str, sealed_token: bytes) -> GateStatus:
        response = await self._call("GET", url, sealed_token, "/__pono/status")
        if response.status_code != 200:
            raise RuntimeUnreachableError(f"gate status answered {response.status_code}")
        try:
            payload = cast(JsonObject, response.json())
        except ValueError as error:
            raise RuntimeUnreachableError("gate status is not JSON") from error
        conflicts = payload.get("conflicts")
        errors = payload.get("errors")
        head = payload.get("head")
        host = payload.get("databaseHost")
        return GateStatus(
            awake=payload.get("awake") is True,
            last_activity_at=_timestamp(payload.get("lastActivityAt")),
            head=head if isinstance(head, str) else None,
            conflicts=tuple(str(c) for c in conflicts) if isinstance(conflicts, list) else (),
            errors=tuple(cast(dict[str, object], e) for e in errors if isinstance(e, dict))
            if isinstance(errors, list)
            else (),
            database_host=host if isinstance(host, str) else None,
        )

    async def write(self, url: str, sealed_token: bytes, path: str, content: bytes | None) -> None:
        body: JsonObject = {"path": path}
        if content is None:
            body["delete"] = True
        else:
            body["content"] = base64.b64encode(content).decode()
        response = await self._call("PUT", url, sealed_token, "/__pono/files", body)
        if response.status_code == 204:
            return
        if response.status_code == 413:
            raise GateRefusedError("runtime.file_too_large")
        if response.status_code == 422:
            raise GateRefusedError("runtime.path_refused")
        raise RuntimeUnreachableError(f"gate write answered {response.status_code}")

    async def _call(
        self,
        method: str,
        url: str,
        sealed_token: bytes,
        path: str,
        body: JsonObject | None = None,
    ) -> httpx.Response:
        token = self._cipher.decrypt(sealed_token).get_secret_value()
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout
            ) as client:
                return await client.request(
                    method,
                    f"{url.rstrip('/')}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    json=body,
                )
        except httpx.HTTPError as error:
            raise RuntimeUnreachableError("gate did not answer") from error


__all__ = ["HttpRuntimeGate"]
