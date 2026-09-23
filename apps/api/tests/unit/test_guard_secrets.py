"""T010 — the secrets guard reads only added lines and never keeps a value (FR-004, SC-006)."""

import pytest

from pono_api.application.guards.secrets import inspect_secrets
from pono_api.application.ports import ChangedFile
from pono_api.domain.releases import GuardStatus

SECRETS = {
    "code_host_token": "ghp_" + "A1b2C3d4" * 5,
    "chat_bot_token": "123456789:" + "AAbbCC_dd-" * 4,
    "cloud_access_key": "AKIA" + "ABCDEFGHIJKLMNOP",
    "payment_key": "sk_live_" + "a1B2c3D4e5F6g7H8",
    "ai_api_key": "sk-ant-" + "a1b2c3d4e5f6" * 3,
    "database_url_password": "postgres://app:s3cr3t-value@db.example.test/app",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----",
}


def _added(path: str, *lines: str, status: str = "added") -> ChangedFile:
    body = "\n".join(f"+{line}" for line in lines)
    return ChangedFile(path, status, f"@@ -0,0 +1,{len(lines)} @@\n{body}")


@pytest.mark.parametrize(("kind", "value"), SECRETS.items())
def test_each_kind_of_secret_is_refused_with_its_place_and_never_its_value(
    kind: str, value: str
) -> None:
    result = inspect_secrets([_added("src/config.ts", "const a = 1;", f'const b = "{value}";')])

    assert result.status is GuardStatus.FAILED
    (finding,) = result.findings
    assert (finding.code, finding.file, finding.line, finding.operation) == (
        "secrets.found",
        "src/config.ts",
        2,
        kind,
    )
    assert value not in repr(result)


def test_a_literal_password_is_refused_but_a_placeholder_or_a_variable_is_not() -> None:
    refused = inspect_secrets([_added("app.py", 'db_password = "Tr0ub4dor&3xyz"')])
    kept = inspect_secrets(
        [
            _added(
                "app.py",
                'password = "changeme"',
                'API_KEY: "${API_KEY}"',
                "token = process.env.TOKEN",
                'secret = "your-secret-here"',
            )
        ]
    )

    assert refused.findings[0].operation == "assigned_secret"
    assert "Tr0ub4dor" not in repr(refused)
    assert kept.status is GuardStatus.PASSED


def test_only_added_lines_count() -> None:
    patch = f'@@ -1,3 +1,3 @@\n keep = 1\n-old = "{SECRETS["payment_key"]}"\n+new = 2\n end = 3\n'
    assert inspect_secrets([ChangedFile("a.py", "modified", patch)]).status is GuardStatus.PASSED


def test_line_numbers_follow_the_hunks() -> None:
    patch = f'@@ -10,2 +40,3 @@\n context\n+fine = 1\n+key = "{SECRETS["code_host_token"]}"\n'
    result = inspect_secrets([ChangedFile("a.py", "modified", patch)])
    assert result.findings[0].line == 42


def test_an_env_file_is_refused_but_its_example_is_read_normally() -> None:
    refused = inspect_secrets([_added(".env", "PORT=3000"), _added("web/.env.local", "A=1")])
    example = inspect_secrets([_added(".env.example", "DATABASE_URL=")])

    assert [f.code for f in refused.findings] == ["secrets.env_file", "secrets.env_file"]
    assert example.status is GuardStatus.PASSED


def test_declared_example_files_are_skipped() -> None:
    fixture = _added("tests/fixtures/keys.txt", f"{SECRETS['private_key']}")
    assert inspect_secrets([fixture]).status is GuardStatus.FAILED
    skipped = inspect_secrets([fixture], example_files=["tests/fixtures/keys.txt"])
    assert skipped.status is GuardStatus.PASSED


def test_binary_and_removed_files_are_skipped_but_an_unreadable_text_file_fails() -> None:
    result = inspect_secrets(
        [
            ChangedFile("logo.png", "added", None),
            ChangedFile("old.txt", "removed", None),
            ChangedFile("huge.sql", "added", None),
        ]
    )

    assert result.status is GuardStatus.FAILED
    assert [(f.code, f.file) for f in result.findings] == [("secrets.unreadable", "huge.sql")]


def test_a_clean_change_passes() -> None:
    assert inspect_secrets([_added("README.md", "Hello")]).status is GuardStatus.PASSED
