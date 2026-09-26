"""T004 — the verdict follows the guards and the approved version, nothing else (FR-002, FR-010)."""

from pono_api.domain.releases import Finding, Guard, GuardResult, GuardStatus, Verdict, verdict

HEAD = "a" * 40


def _all(status: GuardStatus) -> list[GuardResult]:
    return [GuardResult(guard, status) for guard in Guard]


def test_every_guard_passed_waits_for_a_person() -> None:
    assert verdict(_all(GuardStatus.PASSED), HEAD, None) is Verdict.AWAITING_APPROVAL


def test_only_an_approval_of_this_exact_version_approves() -> None:
    passed = _all(GuardStatus.PASSED)
    assert verdict(passed, HEAD, HEAD) is Verdict.APPROVED
    assert verdict(passed, HEAD, "b" * 40) is Verdict.AWAITING_APPROVAL  # an older version


def test_one_failure_refuses_whatever_the_approval() -> None:
    results = [*_all(GuardStatus.PASSED)[:2], GuardResult.failed(Guard.PREVIEW, "preview.down")]
    assert verdict(results, HEAD, HEAD) is Verdict.REFUSED


def test_a_pending_or_missing_guard_keeps_evaluating() -> None:
    assert verdict(_all(GuardStatus.PASSED)[:2], HEAD, None) is Verdict.EVALUATING
    pending = [
        *_all(GuardStatus.PASSED)[:2],
        GuardResult.pending(Guard.PREVIEW, "preview.building"),
    ]
    assert verdict(pending, HEAD, HEAD) is Verdict.EVALUATING


def test_a_failure_without_findings_still_says_why() -> None:
    result = GuardResult.failed(Guard.MIGRATIONS, "migrations.unreadable")
    assert result.findings == (Finding("migrations.unreadable"),)
    assert result.findings[0].as_dict()["code"] == "migrations.unreadable"
