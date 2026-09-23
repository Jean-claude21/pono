"""T012 — the preview of the head commit must answer (FR-006, research R-05)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pono_api.application.guards.preview import PREVIEW_GRACE, inspect_preview
from pono_api.application.ports import DeploymentRecord, PreviewState, ProviderUnavailableError
from pono_api.domain.releases import PREVIEW_TIMEOUT, GuardStatus
from tests.fakes import FakeLinks

NOW = datetime(2026, 9, 23, 12, tzinfo=UTC)
HEAD = "c" * 40


@dataclass
class Host:
    previews: dict[tuple[int, str], PreviewState] = field(default_factory=dict)
    down: bool = False

    async def find_preview(self, ref: str, change_number: int, head_sha: str) -> PreviewState:
        if self.down:
            raise ProviderUnavailableError("down")
        return self.previews.get((change_number, head_sha), PreviewState("absent"))

    async def rollback(self, ref: str, target: DeploymentRecord) -> str:
        raise NotImplementedError


async def _check(
    host: Host | None, age: timedelta, links: FakeLinks | None = None
) -> tuple[GuardStatus, str | None]:
    result = await inspect_preview(
        host,
        "site",
        7,
        HEAD,
        links or FakeLinks(),
        NOW - age,
        NOW,  # type: ignore[arg-type]
    )
    return result.status, result.reason


async def test_a_ready_preview_that_answers_passes() -> None:
    host = Host({(7, HEAD): PreviewState("ready", "https://deploy-preview-7.site.test")})
    assert await _check(host, timedelta(minutes=1)) == (GuardStatus.PASSED, "preview.ready")


async def test_a_ready_preview_that_does_not_answer_fails() -> None:
    url = "https://deploy-preview-7.site.test"
    host = Host({(7, HEAD): PreviewState("ready", url)})
    assert await _check(host, timedelta(minutes=1), FakeLinks(down={url})) == (
        GuardStatus.FAILED,
        "preview.down",
    )


async def test_only_the_preview_of_the_head_commit_counts() -> None:
    host = Host({(7, "older"): PreviewState("ready", "https://old.site.test")})
    assert await _check(host, timedelta(minutes=1)) == (GuardStatus.PENDING, "preview.building")


async def test_a_missing_preview_waits_a_little_then_blocks() -> None:
    assert await _check(Host(), PREVIEW_GRACE - timedelta(seconds=1)) == (
        GuardStatus.PENDING,
        "preview.building",
    )
    assert await _check(Host(), PREVIEW_GRACE + timedelta(seconds=1)) == (
        GuardStatus.FAILED,
        "preview.missing",
    )


async def test_a_project_without_hosting_has_no_preview() -> None:
    assert await _check(None, timedelta(0)) == (GuardStatus.FAILED, "preview.missing")


async def test_a_build_that_fails_or_never_ends_blocks() -> None:
    failed = Host({(7, HEAD): PreviewState("failed")})
    building = Host({(7, HEAD): PreviewState("building")})
    assert await _check(failed, timedelta(minutes=1)) == (GuardStatus.FAILED, "preview.failed")
    assert await _check(building, timedelta(minutes=5)) == (
        GuardStatus.PENDING,
        "preview.building",
    )
    assert await _check(building, PREVIEW_TIMEOUT + timedelta(seconds=1)) == (
        GuardStatus.FAILED,
        "preview.timeout",
    )


async def test_a_host_that_does_not_answer_keeps_the_guard_blocking() -> None:
    assert await _check(Host(down=True), timedelta(hours=2)) == (
        GuardStatus.PENDING,
        "provider.unavailable",
    )
