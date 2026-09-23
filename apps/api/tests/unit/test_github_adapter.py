"""The GitHub App adapter's reads: installations, repositories, files, activity, proposals."""

from datetime import UTC, datetime

import httpx
import jwt
import pytest

from pono_api.application.ports import ProviderUnavailableError, RepositoryInfo
from pono_api.infrastructure.providers.github import GitHubCodeHost
from tests.github_stub import GitHubStub, private_key

pytestmark = pytest.mark.unit

REPO = "/repos/alice/lectio-reads"


async def test_installation_tokens_are_minted_once_from_a_short_app_jwt() -> None:
    stub = GitHubStub()
    stub.on("GET", "/installation/repositories?per_page=100&page=1", body={"repositories": []})
    adapter = stub.adapter()

    await adapter.list_repositories("inst-1")
    await adapter.list_repositories("inst-1")

    minted = [r for r in stub.requests if r.url.path.endswith("/access_tokens")]
    assert len(minted) == 1
    app_jwt = minted[0].headers["authorization"].removeprefix("Bearer ")
    claims = jwt.decode(app_jwt, options={"verify_signature": False})
    assert claims["iss"] == "42"
    assert claims["exp"] - claims["iat"] <= 600
    listing = [r for r in stub.requests if r.url.path == "/installation/repositories"]
    assert {r.headers["authorization"] for r in listing} == {"Bearer installation-token"}


async def test_find_installation_matches_the_person_account() -> None:
    stub = GitHubStub()
    stub.on(
        "GET",
        "/app/installations?per_page=100&page=1",
        body=[
            {"id": 11, "account": {"id": 999, "login": "someone"}},
            {"id": 163926484, "account": {"id": 1001, "login": "alice"}},
        ],
    )
    adapter = stub.adapter()

    assert await adapter.find_installation("1001") == "163926484"
    assert await adapter.find_installation("1002") is None


async def test_installation_status_and_revocation() -> None:
    stub = GitHubStub()
    stub.on("GET", "/app/installations/inst-1", body={"id": 1})
    stub.on("DELETE", "/app/installations/inst-1", 204)
    adapter = stub.adapter()

    assert await adapter.installation_active("inst-1") is True
    assert await adapter.installation_active("gone") is False
    await adapter.revoke_installation("inst-1")
    assert ("DELETE", "/app/installations/inst-1") in [
        (r.method, r.url.path) for r in stub.requests
    ]


async def test_repositories_are_listed_across_pages() -> None:
    stub = GitHubStub()
    first = [{"full_name": f"alice/r{i}", "default_branch": "main"} for i in range(100)]
    stub.on("GET", "/installation/repositories?per_page=100&page=1", body={"repositories": first})
    stub.on(
        "GET",
        "/installation/repositories?per_page=100&page=2",
        body={"repositories": [{"full_name": "alice/lectio-reads", "default_branch": "dev"}]},
    )

    repositories = await stub.adapter().list_repositories("inst-1")

    assert len(repositories) == 101
    assert repositories[-1] == RepositoryInfo("alice/lectio-reads", "dev")


async def test_files_are_read_raw_and_a_missing_file_is_none() -> None:
    stub = GitHubStub()
    stub.on_text("GET", f"{REPO}/contents/.fluxio/project.json", '{"fluxioVersion": 1}')
    stub.on_text("GET", f"{REPO}/contents/.pono/project.json?ref=main", "{}")
    adapter = stub.adapter()

    assert await adapter.read_file("inst-1", "alice/lectio-reads", ".fluxio/project.json") == (
        '{"fluxioVersion": 1}'
    )
    assert await adapter.read_file(
        "inst-1", "alice/lectio-reads", ".pono/project.json", "main"
    ) == ("{}")
    assert await adapter.read_file("inst-1", "alice/lectio-reads", "stack.hcl") is None
    raw = next(r for r in stub.requests if "fluxio" in r.url.path)
    assert raw.headers["accept"] == "application/vnd.github.raw+json"


async def test_last_push_covers_every_branch() -> None:
    stub = GitHubStub()
    stub.on("GET", REPO, body={"pushed_at": "2026-09-14T20:17:22Z"})
    assert await stub.adapter().last_push_at("inst-1", "alice/lectio-reads") == datetime(
        2026, 9, 14, 20, 17, 22, tzinfo=UTC
    )


async def test_commit_author_prefers_the_account_then_the_git_name() -> None:
    stub = GitHubStub()
    stub.on("GET", f"{REPO}/commits/aaa", body={"author": {"login": "alice"}})
    stub.on(
        "GET", f"{REPO}/commits/bbb", body={"author": None, "commit": {"author": {"name": "A"}}}
    )
    stub.on("GET", f"{REPO}/commits/ccc", body={"author": None, "commit": {}})
    adapter = stub.adapter()

    assert await adapter.commit_author("inst-1", "alice/lectio-reads", "aaa") == "alice"
    assert await adapter.commit_author("inst-1", "alice/lectio-reads", "bbb") == "A"
    assert await adapter.commit_author("inst-1", "alice/lectio-reads", "ccc") is None
    assert await adapter.commit_author("inst-1", "alice/lectio-reads", "zzz") is None


@pytest.mark.parametrize(
    ("payload", "state"),
    [
        ({"state": "closed", "merged": True}, "merged"),
        ({"state": "closed", "merged": False}, "closed"),
        ({"state": "open", "merged": False}, "open"),
    ],
)
async def test_proposal_state(payload: dict[str, object], state: str) -> None:
    stub = GitHubStub()
    stub.on("GET", f"{REPO}/pulls/7", body=payload)
    url = "https://github.com/alice/lectio-reads/pull/7"
    assert await stub.adapter().proposal_state("inst-1", url) == state


async def test_malformed_proposal_url_and_failures_are_unavailability() -> None:
    stub = GitHubStub()
    stub.on("GET", REPO, 500, {})
    adapter = stub.adapter()

    with pytest.raises(ProviderUnavailableError):
        await adapter.proposal_state("inst-1", "https://github.com/alice")
    with pytest.raises(ProviderUnavailableError):
        await adapter.last_push_at("inst-1", "alice/lectio-reads")
    with pytest.raises(ProviderUnavailableError):
        await adapter.list_repositories("unknown-installation")


async def test_network_failure_is_unavailability() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    adapter = GitHubCodeHost(
        app_id="42", private_key=private_key(), transport=httpx.MockTransport(fail)
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.find_installation("1001")


def test_credentials_are_required() -> None:
    from pydantic import SecretStr

    with pytest.raises(ValueError, match="credentials"):
        GitHubCodeHost(app_id="", private_key=SecretStr("key"))
