"""T081 — the verified primary address, even when the profile keeps it private (FR-025)."""

import httpx
import pytest
from pydantic import SecretStr

from pono_api.infrastructure.providers.github_identity import GitHubIdentity

pytestmark = pytest.mark.unit


def identity(emails_status: int, emails: object, profile_email: str | None) -> GitHubIdentity:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(200, json={"id": 1001, "login": "alice", "email": profile_email})
        return httpx.Response(emails_status, json=emails)

    return GitHubIdentity(
        "client",
        SecretStr("secret"),
        api_url="https://api.test",
        transport=httpx.MockTransport(handle),
    )


async def test_a_public_profile_address_is_used_as_is() -> None:
    user = await identity(200, [], "public@example.test").fetch_user("token")
    assert user.email == "public@example.test"


async def test_a_private_address_comes_from_the_verified_primary_one() -> None:
    emails = [
        {"email": "old@example.test", "primary": False, "verified": True},
        {"email": "unverified@example.test", "primary": True, "verified": False},
        {"email": "alice@example.test", "primary": True, "verified": True},
    ]
    user = await identity(200, emails, None).fetch_user("token")
    assert user.email == "alice@example.test"


@pytest.mark.parametrize(("status", "body"), [(403, {"message": "no permission"}), (200, {})])
async def test_without_the_permission_the_address_stays_unknown(status: int, body: object) -> None:
    user = await identity(status, body, None).fetch_user("token")
    assert user.email is None
