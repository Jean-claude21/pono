"""Agents acting on a workshop: what they may do, and who did what (003 FR-003, FR-009, FR-012).

The domain names no agent and no vendor: an agent is a registered client with a name, acting under
the access a person granted.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from pono_api.domain.releases import ActorKind

READ_SCOPE = "pono:read"
ACT_SCOPE = "pono:act"
ALL_SCOPES = (READ_SCOPE, ACT_SCOPE)

ACCESS_TOKEN_LIFETIME = timedelta(hours=1)
REFRESH_TOKEN_LIFETIME = timedelta(days=30)
CONSENT_REQUEST_LIFETIME = timedelta(minutes=10)
AUTHORIZATION_CODE_LIFETIME = timedelta(minutes=5)
ROLLBACK_REQUEST_LIFETIME = timedelta(hours=24)


class Access(StrEnum):
    """What a person grants an agent at consent."""

    READ = "read"
    ACT = "act"

    @property
    def scopes(self) -> tuple[str, ...]:
        return (READ_SCOPE,) if self is Access.READ else ALL_SCOPES

    @classmethod
    def of(cls, scopes: tuple[str, ...] | list[str]) -> Access:
        return cls.ACT if ACT_SCOPE in scopes else cls.READ


@dataclass(frozen=True, slots=True)
class Actor:
    """Who does an action: a person in the console, or an agent under a person's access."""

    kind: ActorKind
    name: str
    granted_by: str | None = None

    @classmethod
    def person(cls, login: str) -> Actor:
        return cls(ActorKind.PERSON, login)

    @classmethod
    def agent(cls, client_name: str, granted_by: str) -> Actor:
        return cls(ActorKind.AGENT, client_name, granted_by)

    def detail(self) -> dict[str, object]:
        """What the journal keeps beside the actor's name."""

        return {"grantedBy": self.granted_by} if self.granted_by else {}


__all__ = [
    "ACCESS_TOKEN_LIFETIME",
    "ACT_SCOPE",
    "ALL_SCOPES",
    "AUTHORIZATION_CODE_LIFETIME",
    "CONSENT_REQUEST_LIFETIME",
    "READ_SCOPE",
    "REFRESH_TOKEN_LIFETIME",
    "ROLLBACK_REQUEST_LIFETIME",
    "Access",
    "Actor",
]
