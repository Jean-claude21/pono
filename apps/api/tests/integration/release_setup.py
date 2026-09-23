"""Shared steps for guarded release tests: lectio-reads imported, one change towards `main`."""

import httpx

from pono_api.application.ports import ChangedFile, ChangeRequest, PreviewState
from pono_api.config import Settings
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.workers.refresh import read_all_releases
from tests.conftest import FakeIdentity
from tests.fakes import World
from tests.integration.workshop_setup import LECTIO, connect_everything, stage_lectio

HEAD = "a" * 40
NEXT_HEAD = "b" * 40
PREVIEW = "https://deploy-preview-7--lectio-reads.netlify.app"


def change(
    number: int = 7, head: str = HEAD, *, state: str = "open", agent: bool = True
) -> ChangeRequest:
    return ChangeRequest(
        number=number,
        url=f"https://code.test/{LECTIO}/pull/{number}",
        title="Add notes",
        author="coding-agent[bot]" if agent else "alice",
        author_is_agent=agent,
        head_sha=head,
        head_branch="feature/notes",
        base_branch="main",
        state=state,  # type: ignore[arg-type]
    )


def added(path: str, *lines: str) -> ChangedFile:
    body = "\n".join(f"+{line}" for line in lines)
    return ChangedFile(path, "added", f"@@ -0,0 +1,{len(lines)} @@\n{body}")


def propose(
    world: World,
    *files: ChangedFile,
    head: str = HEAD,
    number: int = 7,
    preview: PreviewState | None = None,
    migrations: dict[str, str] | None = None,
) -> None:
    """An agent opens (or updates) change `number` towards `main`, with its files and preview."""

    world.code_host.changes[LECTIO] = [change(number, head)]
    world.code_host.change_file_sets[(LECTIO, number)] = list(files)
    for path, sql in (migrations or {}).items():
        world.code_host.files[(LECTIO, path)] = sql
    world.factory.hosting_adapters["netlify"].previews[(number, head)] = preview or PreviewState(
        "ready", PREVIEW
    )


async def lectio(client: httpx.AsyncClient, identity: FakeIdentity, world: World) -> str:
    await connect_everything(client, identity)
    stage_lectio(world)
    project = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()
    return str(project["id"])


async def read_releases(settings: Settings, world: World) -> None:
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        await read_all_releases(create_session_factory(engine), world.providers)
    finally:
        await engine.dispose()


async def only_release(client: httpx.AsyncClient, project_id: str) -> dict[str, object]:
    (release,) = (await client.get(f"/api/v1/projects/{project_id}/releases")).json()
    return dict(release)


async def journal(client: httpx.AsyncClient, project_id: str) -> list[str]:
    """Event kinds, oldest first."""

    entries = (await client.get(f"/api/v1/projects/{project_id}/journal")).json()
    return [entry["kind"] for entry in reversed(entries)]


__all__ = [
    "HEAD",
    "NEXT_HEAD",
    "PREVIEW",
    "added",
    "change",
    "journal",
    "lectio",
    "only_release",
    "propose",
    "read_releases",
]
