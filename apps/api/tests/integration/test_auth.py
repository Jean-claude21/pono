"""T027 — sign-in: allow-list, first-time organization, sessions, sign-out.

Covers FR-006, FR-008 and FR-009.
"""

import httpx
import pytest

from pono_api.application.identity import CodeHostUser
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as

pytestmark = [pytest.mark.integration, requires_database]

ALICE = CodeHostUser("1001", "alice", "alice@example.test")


async def test_first_sign_in_creates_person_organization_and_owner_membership(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    response = await sign_in_as(client, identity, ALICE)

    assert response.status_code == 302
    assert response.headers["location"] == "http://console.test/workshop"
    assert "pono_session" in response.cookies
    people = await owner_fetch("SELECT login, email FROM people")
    memberships = await owner_fetch("SELECT role FROM memberships")
    organizations = await owner_fetch("SELECT name FROM organizations")
    assert [(row["login"], row["email"]) for row in people] == [("alice", "alice@example.test")]
    assert [row["role"] for row in memberships] == ["owner"]
    assert [row["name"] for row in organizations] == ["alice"]


async def test_second_sign_in_reuses_the_person(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)
    await sign_in_as(client, identity, CodeHostUser("1001", "Alice", None))

    people = await owner_fetch("SELECT login, email FROM people")
    organizations = await owner_fetch("SELECT id FROM organizations")
    assert [(row["login"], row["email"]) for row in people] == [("Alice", "alice@example.test")]
    assert len(organizations) == 1


async def test_login_outside_the_allow_list_is_refused_and_creates_nothing(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    response = await sign_in_as(client, identity, CodeHostUser("666", "mallory", None))

    assert response.status_code == 302
    assert response.headers["location"] == "http://console.test/?error=auth.not_allowed"
    assert await owner_fetch("SELECT id FROM people") == []


async def test_state_mismatch_is_refused(clean_database: None, client: httpx.AsyncClient) -> None:
    await client.get("/api/v1/auth/login")
    response = await client.get("/api/v1/auth/callback", params={"code": "ok", "state": "forged"})

    assert response.headers["location"] == "http://console.test/?error=auth.state_mismatch"


async def test_provider_refusal_is_reported(
    clean_database: None, client: httpx.AsyncClient
) -> None:
    login = await client.get("/api/v1/auth/login")
    state = login.cookies["pono_oauth_state"]
    response = await client.get("/api/v1/auth/callback", params={"code": "refused", "state": state})

    assert response.headers["location"] == "http://console.test/?error=auth.provider_refused"


async def test_me_locale_and_logout(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)

    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["login"] == "alice"
    assert me.json()["locale"] is None

    assert (await client.put("/api/v1/me/locale", json={"locale": "en"})).status_code == 204
    assert (await client.get("/api/v1/me")).json()["locale"] == "en"

    unsupported = await client.put("/api/v1/me/locale", json={"locale": "de"})
    assert unsupported.status_code == 422
    assert unsupported.json() == {"error": {"code": "request.invalid", "field": "locale"}}

    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    after = await client.get("/api/v1/me")
    assert after.status_code == 401
    assert after.json() == {"error": {"code": "auth.session_required"}}


async def test_the_saved_language_follows_the_person_at_sign_in(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    first = await sign_in_as(client, identity, ALICE)
    assert "pono_locale" not in first.cookies
    await client.put("/api/v1/me/locale", json={"locale": "en"})

    again = await sign_in_as(client, identity, ALICE)

    assert again.cookies["pono_locale"] == "en"


async def test_a_valid_session_skips_the_code_host_on_sign_in(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    anonymous = await client.get("/api/v1/auth/login")
    assert anonymous.headers["location"].startswith("https://code-host.test/authorize")

    await sign_in_as(client, identity, ALICE)
    returning = await client.get("/api/v1/auth/login")

    assert returning.status_code == 302
    assert returning.headers["location"] == "http://console.test/workshop"

    await client.post("/api/v1/auth/logout")
    signed_out = await client.get("/api/v1/auth/login")
    assert signed_out.headers["location"].startswith("https://code-host.test/authorize")


async def test_the_person_sets_where_alerts_go(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, CodeHostUser("1001", "alice", None))
    assert (await client.get("/api/v1/me")).json()["email"] is None

    saved = await client.put("/api/v1/me/email", json={"email": "alerts@example.test"})
    refused = await client.put("/api/v1/me/email", json={"email": "not an address"})

    assert saved.status_code == 204
    assert refused.json() == {"error": {"code": "request.invalid", "field": "email"}}
    assert (await client.get("/api/v1/me")).json()["email"] == "alerts@example.test"


async def test_revoked_session_cannot_be_reused(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    response = await sign_in_as(client, identity, ALICE)
    token = response.cookies["pono_session"]
    await client.post("/api/v1/auth/logout")

    client.cookies.set("pono_session", token)
    replay = await client.get("/api/v1/me")
    assert replay.status_code == 401


async def test_health_reports_the_database(
    client: httpx.AsyncClient, migrated_database: None
) -> None:
    body = (await client.get("/api/v1/health")).json()
    assert body == {
        "status": "ok",
        "database": "ok",
        "email": "not_configured",
        "chat": "not_configured",
    }
