"""T009 — the evidence journal is append-only, for the service and for the base's owner alike
(002 FR-018, SC-007)."""

import asyncpg
import httpx
import pytest

from tests.conftest import APP_URL, OWNER_URL, FakeIdentity, requires_database
from tests.fakes import World
from tests.integration.release_setup import lectio

pytestmark = [pytest.mark.security, requires_database]


async def _try(url: str | None, statement: str) -> str:
    assert url is not None
    connection = await asyncpg.connect(url)
    try:
        async with connection.transaction():
            # The service role only acts inside an organization it names.
            organization = await connection.fetchval("SELECT organization_id FROM project_events")
            await connection.execute(
                "SELECT set_config('pono.organization_ids', $1, true)", f"{{{organization}}}"
            )
            await connection.execute(statement)
        return "done"
    except asyncpg.PostgresError as error:
        return type(error).__name__
    finally:
        await connection.close()


async def test_no_role_can_rewrite_or_erase_the_journal(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await lectio(client, identity, world)  # the import records `protection.missing`

    for url in (APP_URL, OWNER_URL):
        assert await _try(url, "UPDATE project_events SET kind = 'forged'") != "done"
        assert await _try(url, "DELETE FROM project_events") != "done"

    assert await _try(OWNER_URL, "UPDATE project_events SET kind = 'forged'") == (
        "InsufficientPrivilegeError"
    )
