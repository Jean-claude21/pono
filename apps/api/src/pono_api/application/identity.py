"""Code host identity port: who is signing in. The domain never learns which provider answered."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CodeHostUser:
    """A person as the code host knows them."""

    user_id: str
    login: str
    email: str | None


class CodeHostIdentity(Protocol):
    """Sign-in with the code host (FR-009, research R-03)."""

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        """Where to send the browser to authorize Pono."""
        ...

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        """Trade the authorization code for a short-lived user token."""
        ...

    async def fetch_user(self, user_token: str) -> CodeHostUser:
        """Read the identity behind a user token."""
        ...


class IdentityProviderError(RuntimeError):
    """The code host refused or failed the sign-in exchange."""


__all__ = ["CodeHostIdentity", "CodeHostUser", "IdentityProviderError"]
