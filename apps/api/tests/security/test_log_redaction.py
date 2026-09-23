"""T076 — no credential reaches a log line (FR-011)."""

import logging

import pytest

from pono_api.infrastructure.logging import RedactingFilter, configure_logging, redact

pytestmark = pytest.mark.security


@pytest.mark.parametrize(
    "secret",
    [
        "ghs_" + "a" * 36,
        "gho_" + "B" * 36,
        "github_pat_" + "c" * 40,
        "Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature",
    ],
)
def test_token_shapes_are_redacted(secret: str) -> None:
    assert secret not in redact(f"calling the provider with {secret} now")


def test_chat_bot_tokens_in_request_paths_are_redacted() -> None:
    token = "123456789:" + "AAbbCC_dd-" * 4
    line = redact(f"HTTP Request: GET https://api.telegram.org/bot{token}/getUpdates")
    assert token not in line
    assert "getUpdates" in line


def test_credentials_inside_urls_are_redacted() -> None:
    line = redact("connecting to postgresql://pono_app:s3cr3t-pass@host.example/pono")
    assert "s3cr3t-pass" not in line
    assert "host.example/pono" in line


@pytest.mark.parametrize("key", ["password", "token", "client_secret", "private_key", "api_key"])
def test_sensitive_keys_are_redacted(key: str) -> None:
    line = redact(f'payload {{"{key}": "value-to-hide"}} sent')
    assert "value-to-hide" not in line


def test_private_key_blocks_are_redacted() -> None:
    block = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----"
    assert "MIIEow" not in redact(f"loaded {block}")


def test_plain_messages_are_untouched() -> None:
    assert redact("imported lectio-reads in 42 s") == "imported lectio-reads in 42 s"


def test_filter_rewrites_formatted_records(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("pono.test.redaction")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO, logger="pono.test.redaction"):
        logger.info("token=%s", "ghs_" + "z" * 36)
    assert "ghs_" not in caplog.text
    assert "[redacted]" in caplog.text


def test_configure_logging_installs_the_filter_on_uvicorn() -> None:
    configure_logging()
    assert any(isinstance(f, RedactingFilter) for f in logging.getLogger("uvicorn").filters)
