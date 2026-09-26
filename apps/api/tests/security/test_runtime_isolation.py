"""T006 — runtimes, their writes and their saves stay inside their organization; the runtime's token
is stored sealed, and saved content is erased (004 FR-019, FR-020)."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pono_api.config import Settings
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.runtime_setup import ready_runtime, save_as_worker
from tests.integration.workshop_setup import BOB
from tests.security.test_isolation import _as_app

pytestmark = [pytest.mark.security, requires_database]

TABLES = ("runtimes", "runtime_writes", "runtime_saves")


async def test_another_organization_never_reaches_a_runtime(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    await client.put(
        f"/api/v1/projects/{project_id}/runtime/files", json={"path": "a.ts", "content": "x"}
    )
    await client.put(
        f"/api/v1/projects/{project_id}/runtime/files", json={"path": "b.ts", "content": "y"}
    )
    await save_as_worker(settings, world, datetime.now(UTC) + timedelta(minutes=2))
    await client.put(
        f"/api/v1/projects/{project_id}/runtime/files", json={"path": "c.ts", "content": "z"}
    )

    await sign_in_as(client, identity, BOB)
    bob_organization = (await client.get("/api/v1/me")).json()["organizationId"]
    base = f"/api/v1/projects/{project_id}/runtime"

    for answer in (
        await client.get(base),
        await client.post(base),
        await client.delete(base),
        await client.put(f"{base}/files", json={"path": "evil.ts", "content": "x"}),
        await client.post(f"{base}/save"),
        await client.get(f"{base}/errors"),
        await client.post(f"{base}/ticket", json={}),
    ):
        assert answer.json() == {"error": {"code": "project.not_found"}}
    for table in TABLES:
        assert await owner_fetch(f"SELECT 1 FROM {table} LIMIT 1"), f"{table} is empty"
        assert await _as_app(bob_organization, f"SELECT * FROM {table}") == [], table
    assert [path for _, path, _ in world.gate.writes] == ["a.ts", "b.ts", "c.ts"]


async def test_the_token_is_sealed_and_saved_content_is_erased(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    await client.put(
        f"/api/v1/projects/{project_id}/runtime/files", json={"path": "a.ts", "content": "x"}
    )
    await save_as_worker(settings, world, datetime.now(UTC) + timedelta(minutes=2))

    (runtime,) = await owner_fetch("SELECT token_ciphertext FROM runtimes")
    (write,) = await owner_fetch("SELECT content, state FROM runtime_writes")
    columns = await owner_fetch(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = 'runtimes' AND column_name LIKE '%token%'"
    )

    assert bytes(runtime["token_ciphertext"]) == b"sealed-1"  # never the token itself
    assert b"token-1" not in bytes(runtime["token_ciphertext"])
    assert [(c["column_name"], c["data_type"]) for c in columns] == [("token_ciphertext", "bytea")]
    assert (write["content"], write["state"]) == (None, "saved")
