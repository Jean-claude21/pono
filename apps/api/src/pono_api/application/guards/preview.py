"""The preview guard (002 FR-006, research R-05): the preview of the head commit must answer.

A host that produces no preview blocks the release (clarification FR-006). Right after a new
commit, a missing preview is given a short grace period before it counts as missing, since hosts
start their build a few moments after the push.
"""

from datetime import datetime, timedelta

from pono_api.application.ports import (
    HostingProvider,
    LinkChecker,
    ProviderAuthorizationError,
    ProviderUnavailableError,
)
from pono_api.domain.projects import LinkStatus
from pono_api.domain.releases import PREVIEW_TIMEOUT, Finding, Guard, GuardResult

PREVIEW_GRACE = timedelta(minutes=10)


async def inspect_preview(
    hosting: HostingProvider | None,
    ref: str | None,
    change_number: int,
    head_sha: str,
    links: LinkChecker,
    head_seen_at: datetime,
    now: datetime,
) -> GuardResult:
    waited = now - head_seen_at
    if hosting is None or ref is None:
        return GuardResult.failed(Guard.PREVIEW, "preview.missing")
    try:
        preview = await hosting.find_preview(ref, change_number, head_sha)
    except ProviderUnavailableError, ProviderAuthorizationError:
        return GuardResult.pending(Guard.PREVIEW, "provider.unavailable")
    if preview.status == "absent":
        if waited < PREVIEW_GRACE:
            return GuardResult.pending(Guard.PREVIEW, "preview.building")
        return GuardResult.failed(Guard.PREVIEW, "preview.missing")
    if preview.status == "failed":
        return GuardResult.failed(Guard.PREVIEW, "preview.failed")
    if preview.status == "building":
        if waited > PREVIEW_TIMEOUT:
            return GuardResult.failed(Guard.PREVIEW, "preview.timeout")
        return GuardResult.pending(Guard.PREVIEW, "preview.building")
    if preview.url is None or await links.check(preview.url) is not LinkStatus.UP:
        return GuardResult.failed(
            Guard.PREVIEW, "preview.down", Finding("preview.down", url=preview.url)
        )
    return GuardResult.passed(Guard.PREVIEW).with_findings(
        "preview.ready", Finding("preview.ready", url=preview.url)
    )


__all__ = ["PREVIEW_GRACE", "inspect_preview"]
