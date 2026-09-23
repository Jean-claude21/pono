"""Release attempts, guards and verdicts (002 FR-001 to FR-012, data-model).

Pure rules: a verdict only ever comes out of guard results and the approved version, so the same
facts always give the same verdict, and nothing but "approved" lets a change reach production.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum

# The code host check that production branches require; only Pono's own app can satisfy it.
RELEASE_CHECK_NAME = "pono/release"
PREVIEW_TIMEOUT = timedelta(minutes=30)
RELEASES_INTERVAL = timedelta(seconds=60)


class Verdict(StrEnum):
    EVALUATING = "evaluating"
    REFUSED = "refused"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"


class Guard(StrEnum):
    SECRETS = "secrets"
    MIGRATIONS = "migrations"
    PREVIEW = "preview"


class GuardStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class ReleaseState(StrEnum):
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class ProtectionStatus(StrEnum):
    PROTECTED = "protected"
    UNPROTECTED = "unprotected"
    UNAVAILABLE_ON_PLAN = "unavailable_on_plan"
    UNKNOWN = "unknown"


class ActorKind(StrEnum):
    PERSON = "person"
    AGENT = "agent"
    PONO = "pono"


@dataclass(frozen=True, slots=True)
class Finding:
    """Where a guard failed. Holds a location and a code, never a value (SC-006)."""

    code: str
    file: str | None = None
    line: int | None = None
    operation: str | None = None
    url: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "file": self.file,
            "line": self.line,
            "operation": self.operation,
            "url": self.url,
        }


@dataclass(frozen=True, slots=True)
class GuardResult:
    guard: Guard
    status: GuardStatus
    reason: str | None = None
    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @classmethod
    def passed(cls, guard: Guard) -> GuardResult:
        return cls(guard, GuardStatus.PASSED)

    @classmethod
    def failed(cls, guard: Guard, reason: str, *findings: Finding) -> GuardResult:
        return cls(guard, GuardStatus.FAILED, reason, findings or (Finding(reason),))

    @classmethod
    def pending(cls, guard: Guard, reason: str) -> GuardResult:
        return cls(guard, GuardStatus.PENDING, reason)

    def with_findings(self, reason: str, *findings: Finding) -> GuardResult:
        """The same status, with what the journal must remember (a declared destruction)."""

        return GuardResult(self.guard, self.status, reason, findings)


def verdict(results: Iterable[GuardResult], head_sha: str, approved_sha: str | None) -> Verdict:
    """Any failure refuses; any pending guard keeps evaluating; then only an approval of this
    exact version approves (FR-002, FR-010). A missing guard counts as pending: fail closed."""

    by_guard = {result.guard: result for result in results}
    statuses = [
        by_guard[guard].status if guard in by_guard else GuardStatus.PENDING for guard in Guard
    ]
    if GuardStatus.FAILED in statuses:
        return Verdict.REFUSED
    if GuardStatus.PENDING in statuses:
        return Verdict.EVALUATING
    if approved_sha is not None and approved_sha == head_sha:
        return Verdict.APPROVED
    return Verdict.AWAITING_APPROVAL


__all__ = [
    "PREVIEW_TIMEOUT",
    "RELEASES_INTERVAL",
    "RELEASE_CHECK_NAME",
    "ActorKind",
    "Finding",
    "Guard",
    "GuardResult",
    "GuardStatus",
    "ProtectionStatus",
    "ReleaseState",
    "Verdict",
    "verdict",
]
