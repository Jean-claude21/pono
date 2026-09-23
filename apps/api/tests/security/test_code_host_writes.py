"""T030 — the code host adapter writes only on `pono/*` branches and cannot merge (FR-029).

GitHub offers no "propose only" permission (research R-03): this guard is what bounds
`contents: write`. It is checked before any request leaves.
"""

import json
from typing import get_type_hints

import pytest

from pono_api.application.ports import CodeHost, ForbiddenWriteError
from pono_api.infrastructure.providers.github import GitHubCodeHost
from tests.github_stub import GitHubStub

pytestmark = pytest.mark.security

REPO = "/repos/alice/lectio-reads"


def _proposal_routes(stub: GitHubStub) -> None:
    stub.on("GET", f"{REPO}/git/ref/heads/main", body={"object": {"sha": "base-sha"}})
    stub.on("POST", f"{REPO}/git/refs", 201, {"ref": "refs/heads/pono/manifest"})
    stub.on("PUT", f"{REPO}/contents/.pono/project.json", 201, {"content": {}})
    stub.on(
        "POST", f"{REPO}/pulls", 201, {"html_url": "https://github.com/alice/lectio-reads/pull/7"}
    )


async def _propose(adapter: GitHubCodeHost, branch: str) -> str:
    return await adapter.propose_file(
        "inst-1",
        "alice/lectio-reads",
        base="main",
        branch=branch,
        path=".pono/project.json",
        content="{}\n",
        title="Add the Pono project manifest",
        body="Proposed by Pono.",
    )


@pytest.mark.parametrize(
    "branch", ["main", "dev", "pono", "pono/", "feature/pono/x", "refs/heads/main"]
)
async def test_a_write_outside_pono_branches_is_refused_before_any_request(branch: str) -> None:
    stub = GitHubStub()
    _proposal_routes(stub)

    with pytest.raises(ForbiddenWriteError):
        await _propose(stub.adapter(), branch)

    assert stub.requests == []


async def test_the_internal_write_path_refuses_a_protected_branch() -> None:
    stub = GitHubStub()
    with pytest.raises(ForbiddenWriteError):
        await stub.adapter()._write("inst-1", "main", "PUT", f"{REPO}/contents/x", {})
    assert stub.requests == []


async def test_a_proposal_writes_only_on_its_pono_branch() -> None:
    stub = GitHubStub()
    _proposal_routes(stub)

    url = await _propose(stub.adapter(), "pono/manifest")

    assert url == "https://github.com/alice/lectio-reads/pull/7"
    writes = stub.writes()
    assert [(request.method, request.url.path) for request in writes] == [
        ("POST", f"{REPO}/git/refs"),
        ("PUT", f"{REPO}/contents/.pono/project.json"),
        ("POST", f"{REPO}/pulls"),
    ]
    bodies = [json.loads(request.content) for request in writes]
    assert bodies[0]["ref"] == "refs/heads/pono/manifest"
    assert bodies[1]["branch"] == "pono/manifest"
    assert (bodies[2]["head"], bodies[2]["base"]) == ("pono/manifest", "main")
    assert all("merge" not in request.url.path for request in stub.requests)


async def test_an_existing_proposal_branch_and_pull_request_are_reused() -> None:
    stub = GitHubStub()
    _proposal_routes(stub)
    stub.on("POST", f"{REPO}/git/refs", 422, {"message": "Reference already exists"})
    stub.on("GET", f"{REPO}/contents/.pono/project.json?ref=pono/manifest", body={"sha": "old"})
    stub.on("POST", f"{REPO}/pulls", 422, {"message": "A pull request already exists"})
    stub.on(
        "GET",
        f"{REPO}/pulls?state=open&head=alice%3Apono/manifest",
        body=[{"html_url": "https://github.com/alice/lectio-reads/pull/3"}],
    )

    url = await _propose(stub.adapter(), "pono/manifest")

    assert url == "https://github.com/alice/lectio-reads/pull/3"
    put = next(request for request in stub.requests if request.method == "PUT")
    assert json.loads(put.content)["sha"] == "old"


def test_the_adapter_and_its_port_expose_no_merge_operation() -> None:
    for subject in (GitHubCodeHost, CodeHost):
        assert [name for name in dir(subject) if "merge" in name.lower()] == []
    assert "merge" not in " ".join(get_type_hints(CodeHost.propose_file)).lower()
