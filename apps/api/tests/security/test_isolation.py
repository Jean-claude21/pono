"""T067 — each person has their own workshop, sealed at the data layer (US5, FR-007, SC-006).

Two people, two organizations. Every cross-organization attempt answers 404 without confirming
that the resource exists, and direct SQL as the application role sees nothing of the other side.
"""

from collections.abc import AsyncIterator
from datetime import date

import asyncpg
import httpx
import pytest

from pono_api.config import Settings
from pono_api.domain.quotas import LimitSource, Metric, QuotaReading
from pono_api.main import create_app
from tests.conftest import APP_URL, FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World, make_world
from tests.integration.workshop_setup import (
    BOB,
    LECTIO,
    connect_everything,
    stage_lectio,
)

pytestmark = [pytest.mark.security, requires_database]

TABLES = (
    "organizations",
    "memberships",
    "people",
    "connections",
    "connection_events",
    "projects",
    "environments",
    "deployments",
    "quota_readings",
    "alerts",
)


@pytest.fixture
async def two_clients(
    settings: Settings, clean_database: None
) -> AsyncIterator[tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World]]:
    world = make_world()
    world.code_host.account_installations["2002"] = "inst-2"
    identity = FakeIdentity()
    app = create_app(settings, identity, world.providers)
    transport = httpx.ASGITransport(app=app)
    async with (
        httpx.AsyncClient(transport=transport, base_url="http://console.test") as alice,
        httpx.AsyncClient(transport=transport, base_url="http://console.test") as bob,
    ):
        yield alice, bob, identity, world
    await app.state.engine.dispose()


async def _alice_with_a_project(
    alice: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> dict[str, str]:
    await connect_everything(alice, identity)
    stage_lectio(world)
    world.factory.database_adapters["neon"].quotas["royal-mouse"] = [
        QuotaReading(
            Metric.DB_COMPUTE_SECONDS,
            340_000,
            360_000,
            LimitSource.FREE_TIER_ESTIMATE,
            date.today(),
        )
    ]
    project = (await alice.post("/api/v1/projects", json={"repository": LECTIO})).json()
    # A requested reading also reads quotas: Alice now has readings and alerts too.
    await alice.post(f"/api/v1/projects/{project['id']}/refresh")
    connection = (await alice.get("/api/v1/connections")).json()[0]
    return {"project": project["id"], "connection": connection["id"]}


async def test_each_person_sees_only_their_workshop(
    two_clients: tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World],
) -> None:
    alice, bob, identity, world = two_clients
    await _alice_with_a_project(alice, identity, world)
    await sign_in_as(bob, identity, BOB)

    workshop = (await bob.get("/api/v1/projects")).json()
    assert workshop["projects"] == []
    assert sum(workshop["counts"].values()) == 0
    assert workshop["verdicts"] == []
    assert (await bob.get("/api/v1/connections")).json() == []
    assert len((await alice.get("/api/v1/projects")).json()["projects"]) == 1


async def test_reaching_another_organization_answers_not_found(
    two_clients: tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World],
) -> None:
    alice, bob, identity, world = two_clients
    ids = await _alice_with_a_project(alice, identity, world)
    await sign_in_as(bob, identity, BOB)
    unknown = "01980000-0000-7000-8000-000000000000"

    for path, known, missing in (
        ("GET", f"/api/v1/projects/{ids['project']}", f"/api/v1/projects/{unknown}"),
        (
            "POST",
            f"/api/v1/projects/{ids['project']}/refresh",
            f"/api/v1/projects/{unknown}/refresh",
        ),
        (
            "DELETE",
            f"/api/v1/connections/{ids['connection']}",
            f"/api/v1/connections/{unknown}",
        ),
    ):
        foreign = await bob.request(path, known)
        absent = await bob.request(path, missing)
        # Same status, same body: nothing tells a foreign resource from a missing one.
        assert foreign.status_code == absent.status_code == 404
        assert foreign.json() == absent.json()

    connections = await owner_fetch("SELECT status FROM connections")
    assert {row["status"] for row in connections} == {"active"}


async def test_the_same_repository_can_live_in_two_organizations(
    two_clients: tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World],
) -> None:
    alice, bob, identity, world = two_clients
    await _alice_with_a_project(alice, identity, world)
    await sign_in_as(bob, identity, BOB)
    assert (await bob.post("/api/v1/connections/code-host")).status_code == 201

    imported = await bob.post("/api/v1/projects", json={"repository": LECTIO})

    assert imported.status_code == 201
    assert len(await owner_fetch("SELECT id FROM projects")) == 2


async def _as_app(organization_id: object, query: str) -> list[asyncpg.Record]:
    assert APP_URL is not None
    connection = await asyncpg.connect(APP_URL)
    try:
        async with connection.transaction():
            await connection.execute(
                "SELECT set_config('pono.person_id', '', true), "
                "set_config('pono.organization_ids', $1, true)",
                "{" + str(organization_id) + "}",
            )
            return list(await connection.fetch(query))
    finally:
        await connection.close()


async def test_direct_sql_as_the_application_role_sees_no_foreign_row_on_any_table(
    two_clients: tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World],
) -> None:
    alice, bob, identity, world = two_clients
    await _alice_with_a_project(alice, identity, world)
    await sign_in_as(bob, identity, BOB)
    bob_organization = (await bob.get("/api/v1/me")).json()["organizationId"]

    for table in TABLES:
        assert await owner_fetch(f"SELECT 1 FROM {table} LIMIT 1"), f"{table} is empty"
        rows = await _as_app(bob_organization, f"SELECT * FROM {table}")
        if table in ("organizations", "memberships"):
            # Bob sees his own organization and membership, and nothing of Alice's.
            assert all(
                str(row.get("organization_id", row.get("id"))) == bob_organization for row in rows
            )
        else:
            assert rows == [], table


async def test_a_row_cannot_point_at_another_organization_even_with_its_identifier(
    two_clients: tuple[httpx.AsyncClient, httpx.AsyncClient, FakeIdentity, World],
) -> None:
    alice, bob, identity, world = two_clients
    ids = await _alice_with_a_project(alice, identity, world)
    await sign_in_as(bob, identity, BOB)
    bob_organization = (await bob.get("/api/v1/me")).json()["organizationId"]

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await _as_app(
            bob_organization,
            "INSERT INTO projects (id, organization_id, code_connection_id, repository, name, "
            "default_branch, manifest, manifest_status) VALUES (gen_random_uuid(), "
            f"'{bob_organization}', '{ids['connection']}', 'bob/steal', 'steal', 'main', "
            "'{}'::jsonb, 'absent')",
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        # Writing a row for Alice's organization is refused by the policy itself.
        alice_organization = (await alice.get("/api/v1/me")).json()["organizationId"]
        await _as_app(
            bob_organization,
            "INSERT INTO connections (id, organization_id, kind, provider, external_ref) "
            f"VALUES (gen_random_uuid(), '{alice_organization}', 'hosting', 'netlify', 'x')",
        )
