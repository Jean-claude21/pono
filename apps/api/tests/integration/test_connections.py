"""Connections (FR-010 to FR-013) and the scheduled readings (FR-022, T046, T077)."""

import httpx
import pytest

from pono_api.application.refresh_project import Providers
from pono_api.config import Settings
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.workers.refresh import refresh_connections, refresh_due_projects
from pono_api.workers.runner import build_jobs
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.workshop_setup import ALICE, LECTIO, connect_everything, stage_lectio

pytestmark = [pytest.mark.integration, requires_database]


async def test_the_code_host_is_linked_without_any_key(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)

    linked = await client.post("/api/v1/connections/code-host")

    assert linked.status_code == 201
    body = linked.json()
    assert (body["kind"], body["provider"], body["externalRef"], body["status"]) == (
        "code_host",
        "github",
        "inst-1",
        "active",
    )
    stored = await owner_fetch("SELECT secret_ciphertext FROM connections")
    assert [row["secret_ciphertext"] for row in stored] == [None]
    again = await client.post("/api/v1/connections/code-host")
    assert again.status_code == 201
    assert len(await owner_fetch("SELECT id FROM connections")) == 1


async def test_linking_before_installing_the_app_says_so(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    world.code_host.account_installations.clear()

    response = await client.post("/api/v1/connections/code-host")

    assert response.status_code == 422
    assert response.json() == {"error": {"code": "connection.code_host_not_installed"}}


async def test_a_code_host_outage_is_reported_as_such(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    world.code_host.unavailable = True

    response = await client.post("/api/v1/connections/code-host")

    assert (response.status_code, response.json()["error"]["code"]) == (503, "provider.unavailable")


@pytest.mark.parametrize(
    ("body", "status", "code", "field"),
    [
        (
            {"kind": "hosting", "provider": "netlify", "authorization": "bad-key"},
            422,
            "connection.authorization_invalid",
            "authorization",
        ),
        (
            {"kind": "hosting", "provider": "vercel", "authorization": "k"},
            422,
            "connection.provider_unsupported",
            "provider",
        ),
        (
            {"kind": "code_host", "provider": "github", "authorization": "k"},
            422,
            "request.invalid",
            "kind",
        ),
    ],
)
async def test_invalid_connections_are_refused(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    body: dict[str, str],
    status: int,
    code: str,
    field: str,
) -> None:
    await sign_in_as(client, identity, ALICE)

    response = await client.post("/api/v1/connections", json=body)

    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "field": field}}
    assert await owner_fetch("SELECT id FROM connections") == []


async def test_an_active_connection_cannot_be_registered_twice_but_a_revoked_one_can(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)
    body = {"kind": "database", "provider": "neon", "authorization": "neon-key"}
    first = (await client.post("/api/v1/connections", json=body)).json()

    duplicate = await client.post("/api/v1/connections", json=body)
    assert (duplicate.status_code, duplicate.json()) == (
        409,
        {"error": {"code": "connection.duplicate"}},
    )

    assert (await client.delete(f"/api/v1/connections/{first['id']}")).status_code == 204
    again = await client.post("/api/v1/connections", json=body)
    assert again.status_code == 201
    assert again.json()["id"] == first["id"]
    assert again.json()["status"] == "active"


async def test_revocation_erases_the_key_and_removes_the_installation(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    connections = (await client.get("/api/v1/connections")).json()
    assert "authorization" not in str(connections)
    # Keys are kept encrypted: no stored byte sequence holds a key in the clear.
    stored = await owner_fetch("SELECT secret_ciphertext FROM connections")
    ciphertexts = [bytes(row["secret_ciphertext"]) for row in stored if row["secret_ciphertext"]]
    assert len(ciphertexts) == 3
    for key in (b"netlify-key", b"coolify-key", b"neon-key"):
        assert all(key not in ciphertext for ciphertext in ciphertexts)

    for connection in connections:
        response = await client.delete(f"/api/v1/connections/{connection['id']}")
        assert response.status_code == 204

    rows = await owner_fetch("SELECT status, secret_ciphertext FROM connections")
    assert {row["status"] for row in rows} == {"revoked"}
    assert all(row["secret_ciphertext"] is None for row in rows)
    assert world.code_host.revoked == ["inst-1"]
    unknown = await client.delete("/api/v1/connections/01980000-0000-7000-8000-000000000000")
    assert (unknown.status_code, unknown.json()) == (
        404,
        {"error": {"code": "connection.not_found"}},
    )


async def test_the_worker_reads_every_due_project_under_its_organization(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    await client.post("/api/v1/projects", json={"repository": LECTIO})
    await owner_fetch("UPDATE projects SET refreshed_at = now() - interval '1 hour'")
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    sessions = create_session_factory(engine)
    providers: Providers = world.providers
    try:
        assert await refresh_due_projects(sessions, providers) == 1
        # Just read: not due again before its interval.
        assert await refresh_due_projects(sessions, providers) == 0

        world.code_host.active = False
        world.factory.hosting_adapters["netlify"].refuse = True
        await refresh_connections(sessions, providers)
    finally:
        await engine.dispose()

    statuses = {
        row["provider"]: row["status"]
        for row in await owner_fetch("SELECT provider, status FROM connections")
    }
    assert statuses == {
        "github": "revoked",
        "netlify": "expired",
        "coolify": "active",
        "neon": "active",
    }


def test_the_worker_registers_its_jobs(settings: Settings) -> None:
    jobs = build_jobs(settings)
    assert [(job.name, job.interval.total_seconds()) for job in jobs] == [
        ("projects", 300),
        ("connections", 3600),
        ("quotas", 3600),
        ("releases", 60),
    ]
    assert build_jobs(Settings(environment="test", database_app_url=None)) == []
