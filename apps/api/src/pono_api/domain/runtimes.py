"""The development runtime of a project: its states, its limits, what may be written into it, and
the ticket that opens it to a member (004 research R-04, R-10).

The domain names no host, database or code host: a runtime runs on "the person's server", reads
"the development database", and saves to "the development branch".
"""

import base64
import hashlib
import hmac
import json
import posixpath
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID


class RuntimeState(StrEnum):
    AWAITING_FILES = "awaiting_files"
    PREPARING = "preparing"
    STARTING = "starting"
    READY = "ready"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    FAILED = "failed"
    UNREACHABLE = "unreachable"


# What counts against the limit: a runtime that holds, or will hold, the person's server.
STARTED_STATES = frozenset(
    {
        RuntimeState.AWAITING_FILES,
        RuntimeState.PREPARING,
        RuntimeState.STARTING,
        RuntimeState.READY,
        RuntimeState.SLEEPING,
        RuntimeState.UNREACHABLE,
    }
)
# A write or an opening needs the gate to answer.
SERVING_STATES = frozenset({RuntimeState.READY, RuntimeState.SLEEPING})

MAX_STARTED_RUNTIMES = 3
RUNTIME_MEMORY = "1g"
SLEEP_AFTER = timedelta(minutes=15)
SAVE_AFTER_QUIET = timedelta(seconds=60)
MAX_WRITE_BYTES = 1024 * 1024
TICKET_LIFETIME = timedelta(minutes=2)

# Paths an agent or a person may never write through the runtime (research R-10).
_REFUSED_PREFIXES = (".git/", ".pono/runtime/", "node_modules/")
_EXAMPLE_ENV = frozenset({".env.example", ".env.sample", ".env.template"})


class PathRefusedError(ValueError):
    """The path is outside the project, or protected."""


def writable_path(path: str) -> str:
    """The normalized relative path a write may target, or `PathRefusedError`."""

    candidate = path.strip().replace("\\", "/")
    if not candidate or candidate.startswith("/") or "\x00" in candidate:
        raise PathRefusedError(path)
    normalized = posixpath.normpath(candidate)
    if normalized in {".", ".."} or normalized.startswith("../"):
        raise PathRefusedError(path)
    parts = normalized.split("/")
    name = parts[-1]
    if any(f"{normalized}/".startswith(prefix) for prefix in _REFUSED_PREFIXES) or ".git" in parts:
        raise PathRefusedError(path)
    if (name == ".env" or name.startswith(".env.")) and name not in _EXAMPLE_ENV:
        raise PathRefusedError(path)
    return normalized


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(token: str, message: str) -> str:
    return _b64(hmac.new(token.encode(), message.encode(), hashlib.sha256).digest())


@dataclass(frozen=True, slots=True)
class RuntimeTicket:
    """A one-time pass from the console to the runtime's gate (the gate checks it the same way)."""

    runtime_id: UUID
    expires_at: datetime
    nonce: str

    @classmethod
    def issue(cls, runtime_id: UUID, now: datetime | None = None) -> RuntimeTicket:
        moment = now or datetime.now(UTC)
        return cls(runtime_id, moment + TICKET_LIFETIME, secrets.token_urlsafe(12))

    def sign(self, token: str) -> str:
        body = _b64(
            json.dumps(
                {"r": str(self.runtime_id), "e": int(self.expires_at.timestamp()), "n": self.nonce},
                separators=(",", ":"),
            ).encode()
        )
        return f"{body}.{_signature(token, body)}"

    @classmethod
    def check(
        cls, value: str, token: str, runtime_id: UUID, now: datetime | None = None
    ) -> RuntimeTicket | None:
        """The ticket when its signature, runtime and expiry hold; None otherwise."""

        body, _, signature = value.partition(".")
        if not body or not hmac.compare_digest(signature, _signature(token, body)):
            return None
        try:
            payload = json.loads(_unb64(body))
            ticket = cls(
                UUID(payload["r"]), datetime.fromtimestamp(int(payload["e"]), UTC), payload["n"]
            )
        except ValueError, KeyError, TypeError:
            return None
        if ticket.runtime_id != runtime_id or ticket.expires_at <= (now or datetime.now(UTC)):
            return None
        return ticket


__all__ = [
    "MAX_STARTED_RUNTIMES",
    "MAX_WRITE_BYTES",
    "RUNTIME_MEMORY",
    "SAVE_AFTER_QUIET",
    "SERVING_STATES",
    "SLEEP_AFTER",
    "STARTED_STATES",
    "TICKET_LIFETIME",
    "PathRefusedError",
    "RuntimeState",
    "RuntimeTicket",
    "writable_path",
]
