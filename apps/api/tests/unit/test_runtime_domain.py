"""T004 — what may be written into a runtime, and the ticket that opens it (004 R-04, R-10)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pono_api.domain.runtimes import (
    STARTED_STATES,
    PathRefusedError,
    RuntimeState,
    RuntimeTicket,
    writable_path,
)

RUNTIME = UUID("01990000-0000-7000-8000-00000000a001")
TOKEN = "runtime-token-for-tests"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("path", "normalized"),
    [
        ("src/routes/index.tsx", "src/routes/index.tsx"),
        ("./src//a.ts", "src/a.ts"),
        ("src\\b.ts", "src/b.ts"),
        (".env.example", ".env.example"),
        ("docs/.gitignore", "docs/.gitignore"),
    ],
)
def test_a_project_path_is_normalized(path: str, normalized: str) -> None:
    assert writable_path(path) == normalized


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/etc/passwd",
        "../outside.ts",
        "src/../../outside.ts",
        ".git/config",
        "sub/.git/hooks/pre-commit",
        ".pono/runtime/gate.mjs",
        "node_modules/vite/index.js",
        ".env",
        ".env.local",
        "apps/web/.env.production",
        "a\x00b",
    ],
)
def test_protected_or_outside_paths_are_refused(path: str) -> None:
    with pytest.raises(PathRefusedError):
        writable_path(path)


def test_a_signed_ticket_opens_its_runtime_once_in_time() -> None:
    ticket = RuntimeTicket.issue(RUNTIME, NOW)
    signed = ticket.sign(TOKEN)

    assert RuntimeTicket.check(signed, TOKEN, RUNTIME, NOW) == ticket
    assert RuntimeTicket.check(signed, "another-token", RUNTIME, NOW) is None
    assert RuntimeTicket.check(signed, TOKEN, UUID(int=1), NOW) is None
    assert RuntimeTicket.check(signed, TOKEN, RUNTIME, NOW + timedelta(minutes=3)) is None
    tampered = signed.replace(signed[3], "A" if signed[3] != "A" else "B", 1)
    assert RuntimeTicket.check(tampered, TOKEN, RUNTIME, NOW) is None
    assert RuntimeTicket.check("not-a-ticket", TOKEN, RUNTIME, NOW) is None


def test_stopped_and_failed_runtimes_do_not_count_against_the_limit() -> None:
    assert RuntimeState.STOPPED not in STARTED_STATES
    assert RuntimeState.FAILED not in STARTED_STATES
    assert RuntimeState.SLEEPING in STARTED_STATES
