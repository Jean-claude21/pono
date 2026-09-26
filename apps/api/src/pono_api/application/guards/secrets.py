"""The secrets guard (002 FR-004, research R-03): no secret value enters production.

Only the lines a change adds are read. A finding names the file, the line and the kind of secret;
the value itself is never kept, returned or logged (SC-006).
"""

import re
from collections.abc import Iterable
from pathlib import PurePosixPath

from pono_api.application.guards.diff import added_lines
from pono_api.application.ports import ChangedFile
from pono_api.domain.releases import Finding, Guard, GuardResult

# (kind, pattern). Kinds are stable codes shown as the finding's operation.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("code_host_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("code_host_token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("chat_bot_token", re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}")),
    ("cloud_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("payment_key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b")),
    ("chat_workspace_token", re.compile(r"\bxox[abprs]-[0-9A-Za-z-]{10,}\b")),
    ("ai_api_key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{24,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "database_url_password",
        re.compile(r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://[^\s:/@]+:[^\s@/]{3,}@"),
    ),
)
_ASSIGNED = re.compile(
    r"(?i)[\w.-]*(?:password|passwd|secret|token|api[_-]?key|private[_-]?key)[\"']?\s*[:=]\s*"
    r"[\"']([^\"'\s]{8,})[\"']"
)
_PLACEHOLDER = re.compile(
    r"(?i)^(?:x+|\*+|\.+|changeme|change-me|placeholder|example.*|your[-_].*|<.*>|\$\{.*\}|"
    r"process\.env.*|env\(.*\)|todo|none|null|undefined|test.*|dummy.*|fake.*)$"
)
_EXAMPLE_ENV_SUFFIXES = (".example", ".sample", ".template", ".dist")
_BINARY_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".avif",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".woff",
        ".woff2",
        ".ttf",
        ".otf",
        ".eot",
        ".mp3",
        ".mp4",
        ".webm",
        ".mov",
        ".wasm",
        ".jar",
    }
)


def _is_env_file(path: str) -> bool:
    name = PurePosixPath(path).name
    return (name == ".env" or name.startswith(".env.")) and not name.endswith(_EXAMPLE_ENV_SUFFIXES)


def is_binary(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in _BINARY_SUFFIXES


def _line_findings(path: str, line: int, content: str) -> Iterable[Finding]:
    for kind, pattern in PATTERNS:
        if pattern.search(content):
            yield Finding("secrets.found", file=path, line=line, operation=kind)
            return
    assigned = _ASSIGNED.search(content)
    if assigned and not _PLACEHOLDER.match(assigned.group(1)):
        yield Finding("secrets.found", file=path, line=line, operation="assigned_secret")


def inspect_secrets(files: Iterable[ChangedFile], example_files: Iterable[str] = ()) -> GuardResult:
    examples = {path.strip("/") for path in example_files}
    findings: list[Finding] = []
    for changed in files:
        if changed.status == "removed" or changed.path in examples:
            continue
        if _is_env_file(changed.path):
            findings.append(Finding("secrets.env_file", file=changed.path))
            continue
        if changed.binary or is_binary(changed.path):
            continue
        if changed.patch is None:
            # A text file too large for the code host to show: what cannot be read is refused.
            findings.append(Finding("secrets.unreadable", file=changed.path))
            continue
        for line, content in added_lines(changed.patch):
            findings.extend(_line_findings(changed.path, line, content))
    if not findings:
        return GuardResult.passed(Guard.SECRETS)
    return GuardResult.failed(Guard.SECRETS, findings[0].code, *findings)


def mask_secrets(text: str) -> str:
    """The same shapes, masked: for text Pono keeps or shows, such as a runtime's errors (004)."""

    masked = text
    for _, pattern in PATTERNS:
        masked = pattern.sub("***", masked)
    return _ASSIGNED.sub(lambda match: match.group(0).replace(match.group(1), "***"), masked)


__all__ = ["PATTERNS", "inspect_secrets", "is_binary", "mask_secrets"]
