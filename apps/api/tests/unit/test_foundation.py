"""Unit tests for configuration, encryption, errors, URL handling, identity and the worker."""

import asyncio
from datetime import timedelta

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from pono_api.api.errors import install_error_handlers
from pono_api.application.identity import IdentityProviderError
from pono_api.config import Settings
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.crypto import CredentialCipher, CredentialCipherError
from pono_api.infrastructure.database.rls import Principal, _organizations_literal
from pono_api.infrastructure.database.session import normalize_asyncpg_url
from pono_api.infrastructure.providers.github_identity import GitHubIdentity
from pono_api.workers.runner import Job, build_jobs, run_jobs

pytestmark = pytest.mark.unit


def test_allowed_logins_are_split_and_case_insensitive() -> None:
    settings = Settings(allowed_logins="Alice, bob ,,")  # type: ignore[arg-type]
    assert settings.allowed_logins == frozenset({"alice", "bob"})
    assert settings.is_allowed("ALICE")
    assert not settings.is_allowed("mallory")


def test_cookie_security_and_callback_follow_the_public_url() -> None:
    https = Settings(public_url="https://pono.example/")
    http = Settings(public_url="http://localhost:3000")
    assert https.secure_cookies and not http.secure_cookies
    assert https.auth_callback_url == "https://pono.example/api/v1/auth/callback"


def test_smtp_is_configured_only_with_host_and_sender() -> None:
    assert not Settings(smtp_host="smtp.example").smtp_configured
    assert Settings(smtp_host="smtp.example", smtp_from="alerts@pono.example").smtp_configured


def test_cipher_round_trip_and_tamper_detection() -> None:
    cipher = CredentialCipher(CredentialCipher.generate_key())
    ciphertext = cipher.encrypt(SecretStr("provider-token"))
    assert b"provider-token" not in ciphertext
    assert cipher.decrypt(ciphertext).get_secret_value() == "provider-token"
    with pytest.raises(CredentialCipherError):
        cipher.decrypt(ciphertext[:-4] + b"AAAA")


def test_asyncpg_url_normalization() -> None:
    url = normalize_asyncpg_url("postgresql://u:p@host/db?sslmode=require&channel_binding=require")
    assert url == "postgresql+asyncpg://u:p@host/db?ssl=require"
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_asyncpg_url("mysql://u:p@host/db")


def test_organizations_literal() -> None:
    principal = Principal(person_id=__import__("uuid").uuid7())
    assert _organizations_literal(principal.organization_ids) == "{}"


async def test_errors_render_codes_never_prose() -> None:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/missing")
    async def missing() -> None:
        raise not_found("project")

    @app.get("/field")
    async def with_field() -> None:
        raise ApiError("locale.unsupported", 422, field="locale")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://t"
    ) as client:
        missing_response = await client.get("/missing")
        field_response = await client.get("/field")
    assert missing_response.status_code == 404
    assert missing_response.json() == {"error": {"code": "project.not_found"}}
    assert field_response.json() == {"error": {"code": "locale.unsupported", "field": "locale"}}


def _identity(handler: httpx.MockTransport) -> GitHubIdentity:
    return GitHubIdentity(
        "client-id",
        SecretStr("client-secret"),
        web_url="https://gh.test",
        api_url="https://api.gh.test",
        transport=handler,
    )


def test_authorization_url_carries_client_state_and_callback() -> None:
    url = _identity(httpx.MockTransport(lambda _: httpx.Response(500))).authorization_url(
        "st4te", "https://pono.example/api/v1/auth/callback"
    )
    assert url.startswith("https://gh.test/login/oauth/authorize?")
    assert "client_id=client-id" in url and "state=st4te" in url


async def test_identity_exchange_and_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "ghu_token"})
        assert request.headers["Authorization"] == "Bearer ghu_token"
        return httpx.Response(200, json={"id": 42, "login": "alice", "email": None})

    identity = _identity(httpx.MockTransport(handler))
    token = await identity.exchange_code("code", "https://pono.example/cb")
    user = await identity.fetch_user(token)
    assert (user.user_id, user.login, user.email) == ("42", "alice", None)


@pytest.mark.parametrize(
    ("status", "body"),
    [(200, {"error": "bad_verification_code"}), (500, {})],
)
async def test_identity_refused_code(status: int, body: dict[str, str]) -> None:
    identity = _identity(httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
    with pytest.raises(IdentityProviderError):
        await identity.exchange_code("code", "https://pono.example/cb")


@pytest.mark.parametrize(
    ("status", "body"),
    [(401, {}), (200, {"login": "no-id"})],
)
async def test_identity_incomplete_user(status: int, body: dict[str, str]) -> None:
    identity = _identity(httpx.MockTransport(lambda _: httpx.Response(status, json=body)))
    with pytest.raises(IdentityProviderError):
        await identity.fetch_user("ghu_token")


async def test_worker_retries_after_failure_and_stops() -> None:
    stop = asyncio.Event()
    calls: list[int] = []

    async def flaky() -> None:
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("first run fails")
        if len(calls) >= 3:
            stop.set()

    await asyncio.wait_for(
        run_jobs([Job("flaky", timedelta(milliseconds=1), flaky)], stop), timeout=5
    )
    assert len(calls) >= 3


async def test_worker_without_jobs_waits_for_stop() -> None:
    stop = asyncio.Event()
    stop.set()
    await asyncio.wait_for(run_jobs([], stop), timeout=1)
    assert build_jobs(Settings()) == []
