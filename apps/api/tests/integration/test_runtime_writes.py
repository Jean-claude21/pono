"""T020 — writes reach the runtime at once, then are saved to the development branch by author,
never lost, never forced, conflicts kept and lifted (004 US2, FR-007 to FR-012, SC-004, D-019)."""

import base64
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from pono_api.config import Settings
from tests.conftest import FakeIdentity, owner_fetch, requires_database
from tests.fakes import World
from tests.integration.agent_setup import connect, settings  # noqa: F401
from tests.integration.release_setup import journal
from tests.integration.runtime_setup import ready_runtime, save_as_worker
from tests.integration.workshop_setup import LECTIO

pytestmark = [pytest.mark.integration, requires_database]

URL = "https://runtime-1.test"


def later() -> datetime:
    """A quiet minute after now: every write made so far is due."""

    return datetime.now(UTC) + timedelta(minutes=2)


async def _write(
    client: httpx.AsyncClient, project_id: str, path: str, text: str
) -> httpx.Response:
    return await client.put(
        f"/api/v1/projects/{project_id}/runtime/files", json={"path": path, "content": text}
    )


async def test_a_write_reaches_the_runtime_then_is_saved_once_with_its_latest_content(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)

    first = await _write(client, project_id, "src/title.ts", "export const title = 'a';")
    await _write(client, project_id, "./src//title.ts", "export const title = 'b';")
    dropped = await client.put(
        f"/api/v1/projects/{project_id}/runtime/files",
        json={"path": "public/logo.bin", "contentBase64": base64.b64encode(b"\x00\x01").decode()},
    )
    removed = await client.delete(
        f"/api/v1/projects/{project_id}/runtime/files", params={"path": "src/old.ts"}
    )

    assert first.json() == {"path": "src/title.ts", "pendingWrites": 1}
    assert dropped.json()["pendingWrites"] == 2
    assert removed.json() == {"path": "src/old.ts", "pendingWrites": 3}
    assert world.gate.writes == [
        (URL, "src/title.ts", b"export const title = 'a';"),
        (URL, "src/title.ts", b"export const title = 'b';"),
        (URL, "public/logo.bin", b"\x00\x01"),
        (URL, "src/old.ts", None),
    ]
    # Nothing is saved before a quiet minute.
    assert await save_as_worker(settings, world, datetime.now(UTC)) == 0
    assert world.code_host.development_commits == []

    assert await save_as_worker(settings, world, later()) == 1

    ((repository, branch, expected, changes, message),) = world.code_host.development_commits
    assert (repository, branch, expected) == (LECTIO, "dev", "head-0")
    assert [(c.path, c.content) for c in changes] == [
        ("src/title.ts", b"export const title = 'b';"),
        ("public/logo.bin", b"\x00\x01"),
        ("src/old.ts", None),
    ]
    assert "Written by alice." in message
    stored = await owner_fetch("SELECT state, content FROM runtime_writes ORDER BY written_at")
    assert [row["content"] for row in stored] == [None, None, None, None]
    assert [row["state"] for row in stored] == ["superseded", "saved", "saved", "saved"]
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert runtime["pendingWrites"] == 0
    assert runtime["lastSave"]["commitSha"] == "commit-1"
    assert runtime["lastSave"]["files"] == 3
    assert (await journal(client, project_id))[-1] == "runtime.changes_saved"
    assert await save_as_worker(settings, world, later()) == 0


@pytest.mark.parametrize(
    ("path", "content", "code"),
    [
        (".env", "SECRET=1", "runtime.path_refused"),
        ("../outside.ts", "x", "runtime.path_refused"),
        (".git/config", "x", "runtime.path_refused"),
        ("big.txt", "BIG", "runtime.file_too_large"),
    ],
)
async def test_protected_paths_and_large_files_never_reach_the_runtime(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
    path: str,
    content: str,
    code: str,
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)

    body = "x" * (1024 * 1024 + 1) if content == "BIG" else content
    refused = await _write(client, project_id, path, body)

    assert (refused.status_code, refused.json()["error"]["code"]) == (422, code)
    assert world.gate.writes == []
    assert await owner_fetch("SELECT 1 FROM runtime_writes") == []


async def test_a_silent_or_unready_runtime_takes_no_write(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    world.gate.unreachable.add(URL)

    silent = await _write(client, project_id, "src/a.ts", "x")
    await client.delete(f"/api/v1/projects/{project_id}/runtime")
    stopped = await _write(client, project_id, "src/a.ts", "x")

    assert (silent.status_code, silent.json()) == (503, {"error": {"code": "runtime.unreachable"}})
    assert stopped.json() == {"error": {"code": "runtime.not_ready"}}
    assert await owner_fetch("SELECT 1 FROM runtime_writes") == []


async def test_a_file_changed_on_the_branch_is_kept_as_a_conflict_until_written_again(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    await _write(client, project_id, "src/a.ts", "mine")
    await _write(client, project_id, "src/b.ts", "new")
    # Someone pushed to the branch meanwhile, touching src/a.ts.
    world.code_host.heads[(LECTIO, "dev")] = "pushed-elsewhere"
    world.code_host.moved_paths = {"src/a.ts"}

    await client.post(f"/api/v1/projects/{project_id}/runtime/save")

    ((_, _, _, changes, _),) = world.code_host.development_commits
    assert [c.path for c in changes] == ["src/b.ts"]
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert (runtime["conflicts"], runtime["pendingWrites"]) == (["src/a.ts"], 1)
    assert (await journal(client, project_id))[-2:] == [
        "runtime.changes_saved",
        "runtime.save_conflict",
    ]
    verdicts = (await client.get("/api/v1/projects")).json()["verdicts"]
    assert {"projectId": project_id, "code": "runtime.save_conflict"} in verdicts

    # Writing the file again, after reading the branch's version, lifts the conflict.
    await _write(client, project_id, "src/a.ts", "merged by hand")
    await client.post(f"/api/v1/projects/{project_id}/runtime/save")

    assert [c.path for c in world.code_host.development_commits[-1][3]] == ["src/a.ts"]
    runtime = (await client.get(f"/api/v1/projects/{project_id}/runtime")).json()
    assert (runtime["conflicts"], runtime["pendingWrites"]) == ([], 0)


async def test_a_stop_saves_first_and_each_author_gets_a_commit(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    project_id = await ready_runtime(client, identity, world, settings)
    agent = await connect(client, name="Claude")

    await _write(client, project_id, "src/console.ts", "by alice")
    by_agent = await agent.tool(
        "write_file", project_id=project_id, path="src/agent.ts", content="by claude"
    )
    await client.delete(f"/api/v1/projects/{project_id}/runtime")

    assert by_agent == {"path": "src/agent.ts", "pendingWrites": 2}
    commits = world.code_host.development_commits
    assert [[c.path for c in commit[3]] for commit in commits] == [
        ["src/console.ts"],
        ["src/agent.ts"],
    ]
    assert "Written by alice." in commits[0][4]
    assert "Claude (agent), with access granted by alice" in commits[1][4]
    events = await owner_fetch(
        "SELECT kind, actor, actor_kind FROM project_events WHERE kind = 'runtime.changes_saved' "
        "ORDER BY id"
    )
    assert [(e["actor"], e["actor_kind"]) for e in events] == [
        ("alice", "person"),
        ("Claude", "agent"),
    ]
    assert (await journal(client, project_id))[-1] == "runtime.stopped"


async def test_the_default_branch_never_receives_a_runtime_write(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,  # noqa: F811
) -> None:
    """Even if the base said otherwise, the code host adapter refuses (D-019)."""

    project_id = await ready_runtime(client, identity, world, settings)
    await _write(client, project_id, "src/a.ts", "x")
    await owner_fetch("UPDATE runtimes SET development_branch = 'main'")

    with pytest.raises(Exception, match="main"):
        await client.post(f"/api/v1/projects/{project_id}/runtime/save")
    assert world.code_host.development_commits == []
