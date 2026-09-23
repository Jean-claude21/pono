"""Log redaction: no credential ever reaches a log line (FR-011).

Mirrors KYA-Platform's sensitive-fragment filter and adds the token shapes Pono handles.
"""

import logging
import re

_SENSITIVE_KEYS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "private_key",
    "secret",
    "token",
)
_REDACTED = "[redacted]"

_PATTERNS = (
    # GitHub tokens: user, installation, OAuth, refresh and fine-grained personal tokens.
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    # Bearer headers and credentials embedded in URLs.
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),
    # Private key blocks.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)
_KEY_VALUE = re.compile(r"(?i)(" + "|".join(_SENSITIVE_KEYS) + r")(\"?\s*[:=]\s*\"?)([^\s\",;&]+)")


def redact(message: str) -> str:
    """Return the message with every recognizable secret replaced."""

    redacted = _KEY_VALUE.sub(lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}", message)
    for pattern in _PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


class RedactingFilter(logging.Filter):
    """Rewrites each record's final message before any handler formats it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


def configure_logging(level: str = "INFO") -> None:
    """Install the redacting filter on the root handler and on uvicorn's loggers."""

    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    redacting = RedactingFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(redacting)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(redacting)


__all__ = ["RedactingFilter", "configure_logging", "redact"]
