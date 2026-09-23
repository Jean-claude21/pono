"""T017, T018, T026, T030 — the adapters of the guarded release, against the payload shapes the real
APIs return (Netlify, Coolify 4.3.23, GitHub), with every key use traced (FR-024)."""

import json

import pytest

from pono_api.application.ports import (
    ForbiddenWriteError,
    ProtectionRefusedError,
    RollbackUnsupportedError,
)
from pono_api.domain.projects import EnvironmentKind
from pono_api.domain.releases import ProtectionStatus
from pono_api.infrastructure.providers.coolify import CoolifyHosting, preview_url
from pono_api.infrastructure.providers.netlify import NetlifyHosting
from tests.fakes import deployment
from tests.github_stub import GitHubStub
from tests.unit.test_providers import DEPLOYS, LECTIO_SITE, Api, recorder

pytestmark = pytest.mark.unit

HEAD = "f" * 40
REPO = "/repos/alice/lectio-reads"


# --- Netlify -----------------------------------------------------------------------------------


def _preview(state: str, commit: str = HEAD, review: int = 7) -> dict[str, object]:
    return {
        "id": f"p-{state}",
        "state": state,
        "context": "deploy-preview",
        "review_id": review,
        "commit_ref": commit,
        "created_at": "2026-09-23T10:00:00Z",
        "deploy_ssl_url": "https://deploy-preview-7--lectio-reads.netlify.app",
    }


@pytest.mark.parametrize(
    ("deploys", "status"),
    [
        ([], "absent"),
        ([_preview("ready", commit="older")], "absent"),
        ([_preview("ready", review=8)], "absent"),
        ([_preview("building")], "building"),
        ([_preview("error")], "failed"),
        ([_preview("ready")], "ready"),
    ],
)
async def test_netlify_finds_the_preview_of_a_change_at_its_head(
    deploys: list[dict[str, object]], status: str
) -> None:
    api = Api({"/api/v1/sites/b743/deploys?per_page=50": [*deploys, *DEPLOYS]})
    actions, record = recorder()
    host = NetlifyHosting("key", record, transport=api.transport)  # type: ignore[arg-type]

    preview = await host.find_preview("b743", 7, HEAD)

    assert preview.status == status
    if status == "ready":
        assert preview.url == "https://deploy-preview-7--lectio-reads.netlify.app"
    assert actions == ["read_deploys"]


async def test_netlify_restores_an_earlier_deploy_and_says_what_is_live() -> None:
    site = {**LECTIO_SITE, "published_deploy": {"id": "d1", "commit_ref": "c1"}}
    api = Api(
        {
            "/api/v1/sites/b743/deploys/d1/restore": {"id": "d1"},
            "/api/v1/sites/b743": site,
            "/api/v1/sites/b743/deploys?per_page=30": DEPLOYS,
        }
    )
    actions, record = recorder()
    host = NetlifyHosting("key", record, transport=api.transport)  # type: ignore[arg-type]

    restored = await host.rollback("b743", deployment("d1", commit="c1"))
    live = await host.read_environment("b743", EnvironmentKind.PRODUCTION, "main")

    assert restored == "d1"
    assert live.live_commit == "c1"
    assert actions[0] == "restore_deploy"


async def test_netlify_cannot_restore_a_deploy_it_no_longer_has() -> None:
    host = NetlifyHosting("key", lambda _: None, transport=Api({}).transport)
    with pytest.raises(RollbackUnsupportedError):
        await host.rollback("b743", deployment("gone"))


# --- Coolify -----------------------------------------------------------------------------------

APPLICATION = {
    "uuid": "app-1",
    "fqdn": "https://lectio.vttlife.com",
    "preview_url_template": "{{pr_id}}.{{domain}}",
}


def _coolify(routes: dict[str, object]) -> tuple[CoolifyHosting, list[str], Api]:
    api = Api(routes)
    actions, record = recorder()
    host = CoolifyHosting(
        "https://app.coolify.test",
        "key",
        record,  # type: ignore[arg-type]
        transport=api.transport,
    )
    return host, actions, api


async def test_coolify_finds_the_preview_deployment_of_a_change_at_its_head() -> None:
    history = {
        "deployments": [
            {
                "deployment_uuid": "d9",
                "status": "finished",
                "pull_request_id": 7,
                "commit": HEAD,
                "created_at": "2026-09-23T10:00:00Z",
            },
            {
                "deployment_uuid": "d8",
                "status": "failed",
                "pull_request_id": 7,
                "commit": "older",
                "created_at": "2026-09-23T09:00:00Z",
            },
        ]
    }
    host, _, _ = _coolify(
        {
            "/api/v1/applications/app-1": APPLICATION,
            "/api/v1/deployments/applications/app-1?skip=0&take=30": history,
        }
    )

    ready = await host.find_preview("app-1", 7, HEAD)
    absent = await host.find_preview("app-1", 9, HEAD)

    assert (ready.status, ready.url) == ("ready", "https://7.lectio.vttlife.com")
    assert absent.status == "absent"
    assert preview_url({"fqdn": None}, 7) is None


async def test_coolify_rolls_back_to_an_image_it_still_keeps() -> None:
    images = {"images": [{"tag": "c1", "is_current": False}, {"tag": "c2", "is_current": True}]}
    host, actions, api = _coolify(
        {
            "/api/v1/applications/app-1/rollback-images": images,
            "/api/v1/applications/app-1/rollback": {"deployment_uuid": "rb-1"},
        }
    )

    assert await host.rollback("app-1", deployment("d1", commit="c1")) == "rb-1"
    assert actions == ["read_images", "rollback"]
    with pytest.raises(RollbackUnsupportedError):
        await host.rollback("app-1", deployment("d0", commit="pruned"))
    with pytest.raises(RollbackUnsupportedError):
        await host.rollback("app-1", deployment("d0", commit=None))
    assert api.paths.count("/api/v1/applications/app-1/rollback") == 1


# --- GitHub --------------------------------------------------------------------------------------


def _pull(number: int, *, merged: bool = False, bot: bool = True) -> dict[str, object]:
    return {
        "number": number,
        "html_url": f"https://github.com/alice/lectio-reads/pull/{number}",
        "title": "Add notes",
        "state": "closed" if merged else "open",
        "merged": merged,
        "user": {"login": "agent[bot]" if bot else "alice", "type": "Bot" if bot else "User"},
        "head": {"sha": HEAD, "ref": "feature/notes"},
        "base": {"ref": "main"},
    }


async def test_github_lists_open_changes_towards_a_branch_and_reads_one() -> None:
    stub = GitHubStub()
    stub.on("GET", f"{REPO}/pulls?state=open&base=main&per_page=100", body=[_pull(7)])
    stub.on("GET", f"{REPO}/pulls/7", body=_pull(7, merged=True, bot=False))

    (change,) = await stub.adapter().list_changes("inst-1", "alice/lectio-reads", "main")
    merged = await stub.adapter().read_change("inst-1", "alice/lectio-reads", 7)

    assert (change.number, change.head_sha, change.author_is_agent, change.state) == (
        7,
        HEAD,
        True,
        "open",
    )
    assert (merged.state, merged.author, merged.author_is_agent) == ("merged", "alice", False)


async def test_github_lists_the_files_of_a_change_with_their_patch() -> None:
    stub = GitHubStub()
    stub.on(
        "GET",
        f"{REPO}/pulls/7/files?per_page=100&page=1",
        body=[
            {"filename": "drizzle/0003.sql", "status": "added", "patch": "@@ -0,0 +1 @@\n+x"},
            {"filename": "logo.png", "status": "added"},
            {"filename": "dump.sql", "status": "added"},
        ],
    )

    files = await stub.adapter().change_files("inst-1", "alice/lectio-reads", 7)

    assert [(f.path, f.patch is not None, f.binary) for f in files] == [
        ("drizzle/0003.sql", True, False),
        ("logo.png", False, True),
        ("dump.sql", False, False),
    ]


async def test_github_publishes_the_release_check_on_the_head_commit() -> None:
    stub = GitHubStub()
    stub.on("POST", f"{REPO}/check-runs", 201, {"id": 1})
    adapter = stub.adapter()

    for state in ("pending", "failure", "success"):
        await adapter.set_release_check(
            "inst-1", "alice/lectio-reads", HEAD, state, summary="s", details_url="https://c.test"
        )

    bodies = [json.loads(request.content) for request in stub.writes()]
    assert [(b["name"], b["head_sha"], b["status"], b.get("conclusion")) for b in bodies] == [
        ("pono/release", HEAD, "in_progress", None),
        ("pono/release", HEAD, "completed", "failure"),
        ("pono/release", HEAD, "completed", "success"),
    ]


PROTECTED = {
    "required_status_checks": {
        "strict": False,
        "checks": [{"context": "pono/release", "app_id": 42}],
    },
    "required_pull_request_reviews": {"required_approving_review_count": 0},
    "enforce_admins": {"enabled": True},
    "allow_force_pushes": {"enabled": False},
    "allow_deletions": {"enabled": False},
}


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (404, {"message": "Branch not protected"}, ProtectionStatus.UNPROTECTED),
        (
            403,
            {"message": "Upgrade to GitHub Pro or make this repository public."},
            ProtectionStatus.UNAVAILABLE_ON_PLAN,
        ),
        (403, {"message": "Resource not accessible by integration"}, ProtectionStatus.UNKNOWN),
        (200, PROTECTED, ProtectionStatus.PROTECTED),
        (
            200,
            {
                **PROTECTED,
                "required_status_checks": {"checks": [{"context": "pono/release", "app_id": 7}]},
            },
            ProtectionStatus.UNPROTECTED,
        ),
        (200, {**PROTECTED, "enforce_admins": {"enabled": False}}, ProtectionStatus.UNPROTECTED),
    ],
)
async def test_github_reads_the_protection_of_the_production_branch(
    status: int, body: dict[str, object], expected: ProtectionStatus
) -> None:
    stub = GitHubStub()
    stub.on("GET", f"{REPO}/branches/main/protection", status, body)
    assert await stub.adapter().read_protection("inst-1", "alice/lectio-reads", "main") is expected


async def test_github_adds_its_rule_without_removing_an_existing_one() -> None:
    stub = GitHubStub()
    existing = {
        "required_status_checks": {"strict": True, "checks": [{"context": "ci", "app_id": 15368}]},
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "restrictions": {"users": [{"login": "alice"}], "teams": [], "apps": []},
    }
    stub.on("GET", f"{REPO}/branches/main/protection", 200, existing)
    stub.on("PUT", f"{REPO}/branches/main/protection", 200, {})

    await stub.adapter().apply_protection("inst-1", "alice/lectio-reads", "main")

    (put,) = stub.writes()
    rule = json.loads(put.content)
    assert rule["required_status_checks"] == {
        "strict": True,
        "checks": [{"context": "ci", "app_id": 15368}, {"context": "pono/release", "app_id": 42}],
    }
    assert rule["required_pull_request_reviews"]["required_approving_review_count"] == 1
    assert rule["restrictions"] == {"users": ["alice"], "teams": [], "apps": []}
    assert (rule["enforce_admins"], rule["allow_force_pushes"], rule["allow_deletions"]) == (
        True,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("Upgrade to GitHub Pro or make this repository public.", "protection.unavailable_on_plan"),
        ("Resource not accessible by integration", "protection.permission_missing"),
    ],
)
async def test_github_refusals_to_protect_are_named(message: str, code: str) -> None:
    stub = GitHubStub()
    stub.on("GET", f"{REPO}/branches/main/protection", 404, {"message": "Branch not protected"})
    stub.on("PUT", f"{REPO}/branches/main/protection", 403, {"message": message})

    with pytest.raises(ProtectionRefusedError) as refused:
        await stub.adapter().apply_protection("inst-1", "alice/lectio-reads", "main")

    assert refused.value.code == code


async def test_the_two_bounded_writes_refuse_anything_else_before_any_request() -> None:
    stub = GitHubStub()
    adapter = stub.adapter()

    with pytest.raises(ForbiddenWriteError):
        await adapter._check_write("inst-1", "alice/lectio-reads", {"name": "ci"})
    with pytest.raises(ForbiddenWriteError):
        await adapter._check_write("inst-1", "alice/lectio-reads/../x", {"name": "pono/release"})
    with pytest.raises(ForbiddenWriteError):
        await adapter._protection_write("inst-1", "alice/lectio-reads", "pono/manifest", {})
    with pytest.raises(ForbiddenWriteError):
        await adapter._protection_write("inst-1", "alice/lectio-reads", "", {})

    assert stub.requests == []
