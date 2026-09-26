"""T015, T023, T026, T027 — a runtime is asked for, proposed, created on the person's server,
opened by a member and stopped; the production database is refused at every step (004 US1, US3, US5,
US6, SC-003)."""

import httpx
import pytest

from pono_api.application import runtimes as runtimes_module
from pono_api.config import Settings
from tests.conftest import FakeIdentity, requires_database
from tests.fakes import World, awake_gate
from tests.integration.release_setup import journal
from tests.integration.runtime_setup import (
    follow,
    host,
    ready_runtime,
    runtime_project,
)
from tests.integration.workshop_setup import LECTIO, NETTIO, stage_nettio

pytestmark = [pytest.mark.integration, requires_database]


async def test_files_are_proposed_then_the_runtime_is_created_on_the_development_database(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await runtime_project(client, identity, world)

    asked = await client.post(f"/api/v1/projects/{project_id}/runtime")

    assert asked.status_code == 202
    runtime = asked.json()
    assert (runtime["state"], runtime["developmentBranch"]) == ("awaiting_files", "dev")
    ((repository, base, branch, files),) = world.code_host.file_proposals
    assert (repository, base, branch) == (LECTIO, "dev", "pono/runtime")
    assert sorted(files) == [
        ".pono/runtime/Dockerfile",
        ".pono/runtime/README.md",
        ".pono/runtime/dev.mjs",
        ".pono/runtime/gate.mjs",
    ]
    assert "pnpm@10.18.3" in files[".pono/runtime/Dockerfile"]
    assert host(world).created == []

    world.code_host.proposal_states[runtime["proposalUrl"]] = "merged"
    await follow(settings, world)

    (spec,) = host(world).created
    assert (spec.branch, spec.memory, spec.clone_url) == (
        "dev",
        "1g",
        f"git@code.test:{LECTIO}.git",
    )
    assert "ep-dev.db.test" in spec.variables["DATABASE_URL"]
    assert "ep-main" not in " ".join(spec.variables.values())
    assert spec.variables["PONO_CONSOLE_URL"] == "http://console.test"
    assert spec.variables["PONO_SLEEP_AFTER_SECONDS"] == "900"
    assert host(world).started == ["app-1"]
    assert list(world.code_host.deploy_keys.values()) == [(LECTIO, "ssh-ed25519 AAAA")]
    starting = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert starting["state"] == "starting"

    host(world).status["app-1"] = "running"
    await follow(settings, world)

    ready = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert (ready["state"], ready["url"], ready["awake"]) == (
        "ready",
        "https://runtime-1.test",
        True,
    )
    assert ready["limits"] == {
        "started": 1,
        "maxStarted": 3,
        "memory": "1g",
        "sleepAfterMinutes": 15,
    }
    assert (await journal(client, project_id))[-3:] == [
        "runtime.requested",
        "runtime.files_proposed",
        "runtime.ready",
    ]


async def test_files_already_in_place_create_the_runtime_at_once(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    project_id = await runtime_project(client, identity, world)
    for path, content in runtimes_module.runtime_files("10.18.3").items():
        world.code_host.files[(LECTIO, path)] = content

    runtime = (await client.post(f"/api/v1/projects/{project_id}/runtime")).json()

    assert runtime["state"] == "starting"
    assert world.code_host.file_proposals == []
    assert len(host(world).created) == 1


@pytest.mark.parametrize(
    ("stage", "code"),
    [
        ("no_package", "runtime.stack_unsupported"),
        ("no_vite", "runtime.stack_unsupported"),
        ("production_host", "runtime.production_database"),
        ("no_development_database", "runtime.database_missing"),
    ],
)
async def test_nothing_is_created_for_an_unproven_stack_or_the_production_database(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    stage: str,
    code: str,
) -> None:
    project_id = await runtime_project(client, identity, world)
    neon = world.factory.database_adapters["neon"]
    if stage == "no_package":
        del world.code_host.files[(LECTIO, "package.json")]
    elif stage == "no_vite":
        world.code_host.files[(LECTIO, "package.json")] = '{"dependencies": {"next": "15"}}'
    elif stage == "production_host":
        neon.branch_hosts["dev"] = neon.branch_hosts["main"]
    else:
        del neon.branch_hosts["dev"]

    refused = await client.post(f"/api/v1/projects/{project_id}/runtime")

    assert refused.status_code == 422
    assert refused.json() == {"error": {"code": code}}
    assert world.code_host.file_proposals == []
    assert host(world).created == []
    missing = await client.get(f"/api/v1/projects/{project_id}/runtime")
    assert missing.json() == {"error": {"code": "runtime.not_found"}}


async def test_the_limit_of_started_runtimes_is_applied(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtimes_module, "MAX_STARTED_RUNTIMES", 1)
    project_id = await runtime_project(client, identity, world)
    stage_nettio(world)
    nettio = (await client.post("/api/v1/projects", json={"repository": NETTIO})).json()["id"]
    await client.post(f"/api/v1/projects/{project_id}/runtime")

    again = await client.post(f"/api/v1/projects/{project_id}/runtime")
    refused = await client.post(f"/api/v1/projects/{nettio}/runtime")

    assert again.json() == {"error": {"code": "runtime.already_started"}}
    assert (refused.status_code, refused.json()) == (
        409,
        {"error": {"code": "runtime.limit_reached"}},
    )


async def test_a_stopped_runtime_starts_again_on_the_same_application(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)

    stopped = (await client.delete(f"/api/v1/projects/{project_id}/runtime")).json()
    started = (await client.post(f"/api/v1/projects/{project_id}/runtime")).json()

    assert stopped["state"] == "stopped"
    assert stopped["limits"]["started"] == 0
    assert host(world).stopped == ["app-1"]
    assert started["state"] == "starting"
    assert host(world).started == ["app-1", "app-1"]
    assert len(host(world).created) == 1
    assert "runtime.stopped" in await journal(client, project_id)


async def test_a_runtime_answering_from_the_production_database_is_stopped_at_once(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    world.gate.statuses["https://runtime-1.test"] = awake_gate(database_host="ep-main.db.test")

    await follow(settings, world)

    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert (runtime["state"], runtime["reason"]) == ("failed", "runtime.production_database")
    assert host(world).stopped == ["app-1"]
    assert (await journal(client, project_id))[-1] == "runtime.failed"
    verdicts = (await client.get("/api/v1/projects")).json()["verdicts"]
    assert {"projectId": project_id, "code": "runtime.failed"} in verdicts


async def test_a_silent_gate_is_unreachable_and_a_stopped_host_is_a_failure(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    world.gate.unreachable.add("https://runtime-1.test")

    await follow(settings, world)
    unreachable = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    host(world).status["app-1"] = "stopped"
    await follow(settings, world)
    failed = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()

    assert unreachable["state"] == "unreachable"
    assert (failed["state"], failed["reason"]) == ("failed", "runtime.stopped_by_host")


async def test_a_closed_proposal_fails_the_runtime(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await runtime_project(client, identity, world)
    runtime = (await client.post(f"/api/v1/projects/{project_id}/runtime")).json()
    world.code_host.proposal_states[runtime["proposalUrl"]] = "closed"

    await follow(settings, world)

    failed = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert (failed["state"], failed["reason"]) == ("failed", "runtime.files_refused")
    assert host(world).created == []


async def test_a_member_gets_a_one_time_ticket_and_sleep_is_reported(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await runtime_project(client, identity, world)
    await client.post(f"/api/v1/projects/{project_id}/runtime")
    early = await client.post(f"/api/v1/projects/{project_id}/runtime/ticket", json={})
    assert early.json() == {"error": {"code": "runtime.not_ready"}}

    project_id = await _ready_again(client, world, settings, project_id)
    opened = await client.post(
        f"/api/v1/projects/{project_id}/runtime/ticket", json={"return": "/books?x=1"}
    )
    world.gate.statuses["https://runtime-1.test"] = awake_gate(awake=False)
    await follow(settings, world)
    asleep = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()

    runtime_id = asleep["id"]
    assert opened.json() == {
        "url": f"https://runtime-1.test/__pono/auth?ticket=ticket-{runtime_id}"
        "&return=%2Fbooks%3Fx%3D1"
    }
    assert (asleep["state"], asleep["awake"]) == ("sleeping", False)
    elsewhere = await client.post(
        f"/api/v1/projects/{project_id}/runtime/ticket", json={"return": "//evil.test"}
    )
    assert elsewhere.json()["url"].endswith("&return=%2F")


async def _ready_again(
    client: httpx.AsyncClient, world: World, settings: Settings, project_id: str
) -> str:
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    world.code_host.proposal_states[runtime["proposalUrl"]] = "merged"
    await follow(settings, world)
    host(world).status["app-1"] = "running"
    await follow(settings, world)
    return project_id


async def test_errors_are_read_live_with_secrets_masked_or_last_known(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    world.gate.statuses["https://runtime-1.test"] = awake_gate(
        errors=(
            {
                "source": "compile",
                "message": "Cannot connect postgresql://owner:hunter2@ep-dev.db.test/app",
                "file": "src/db.ts",
                "line": 4,
                "count": 2,
                "resolved": False,
            },
        )
    )

    live = (await client.get(f"/api/v1/projects/{project_id}/runtime/errors")).json()
    world.gate.unreachable.add("https://runtime-1.test")
    known = (await client.get(f"/api/v1/projects/{project_id}/runtime/errors")).json()

    assert live["live"] is True
    (error,) = live["errors"]
    assert "hunter2" not in error["message"]
    assert (error["file"], error["line"], error["count"]) == ("src/db.ts", 4, 2)
    assert known == {"errors": live["errors"], "live": False}
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert runtime["errorCount"] == 1
