"""Shared steps for runtime tests: lectio-reads on the proven stack, its runtime ready."""

import json
from datetime import datetime

import httpx

from pono_api.application.runtime_writes import save_due
from pono_api.config import Settings
from pono_api.infrastructure.database.rls import Principal
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.workers.refresh import follow_all_runtimes
from tests.conftest import FakeIdentity, owner_fetch
from tests.fakes import FakeRuntimeHost, World
from tests.integration.release_setup import lectio
from tests.integration.workshop_setup import LECTIO

PACKAGE = json.dumps(
    {
        "name": "lectio-reads",
        "packageManager": "pnpm@10.18.3",
        "devDependencies": {"vite": "^7.0.0"},
    }
)


def on_proven_stack(world: World) -> None:
    world.code_host.files[(LECTIO, "package.json")] = PACKAGE
    world.code_host.files[(LECTIO, "pnpm-lock.yaml")] = "lockfileVersion: '9.0'\n"


def host(world: World) -> FakeRuntimeHost:
    return world.factory.runtime_hosts["coolify"]


async def runtime_project(client: httpx.AsyncClient, identity: FakeIdentity, world: World) -> str:
    project_id = await lectio(client, identity, world)
    on_proven_stack(world)
    return project_id


async def follow(settings: Settings, world: World) -> None:
    """One tick of the worker's runtime job."""

    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        await follow_all_runtimes(create_session_factory(engine), world.providers)
    finally:
        await engine.dispose()


async def save_as_worker(settings: Settings, world: World, now: datetime) -> int:
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        organization = (await owner_fetch("SELECT id FROM organizations LIMIT 1"))[0]["id"]
        return await save_due(
            create_session_factory(engine),
            Principal.for_organization(organization),
            world.providers,
            now,
        )
    finally:
        await engine.dispose()


async def ready_runtime(
    client: httpx.AsyncClient, identity: FakeIdentity, world: World, settings: Settings
) -> str:
    """Asked for, files merged, created, running: the runtime serves."""

    project_id = await runtime_project(client, identity, world)
    asked = (await client.post(f"/api/v1/projects/{project_id}/runtime")).json()
    world.code_host.proposal_states[asked["proposalUrl"]] = "merged"
    await follow(settings, world)
    host(world).status["app-1"] = "running"
    await follow(settings, world)
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert runtime["state"] == "ready", runtime
    return project_id


__all__ = [
    "PACKAGE",
    "follow",
    "host",
    "on_proven_stack",
    "ready_runtime",
    "runtime_project",
    "save_as_worker",
]
