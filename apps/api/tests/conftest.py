"""Shared fixtures. Database tests run against a real Postgres with the two production roles.

Locally they target the disposable Neon `test` branch; in CI, a Postgres service container.
Both expose PONO_TEST_OWNER_URL and PONO_TEST_APP_URL.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import asyncpg
import httpx
import pytest
from alembic import command
from alembic.config import Config
from pydantic import SecretStr

from pono_api.application.identity import CodeHostUser, IdentityProviderError
from pono_api.config import Settings
from pono_api.main import create_app
from tests.fakes import World, make_world

API_ROOT = Path(__file__).resolve().parents[1]
TABLES_TO_CLEAN = (
    "project_events",
    "rollbacks",
    "release_approvals",
    "release_checks",
    "releases",
    "alerts",
    "quota_readings",
    "deployments",
    "environments",
    "projects",
    "connection_events",
    "connections",
    "sessions",
    "memberships",
    "organizations",
    "people",
)


def _raw_url(variable: str) -> str | None:
    value = os.environ.get(variable)
    if not value:
        return None
    # asyncpg does not understand channel_binding; the service strips it the same way.
    parts = urlsplit(value)
    query = "&".join(
        f"{key}={values[0]}"
        for key, values in parse_qs(parts.query).items()
        if key != "channel_binding"
    )
    return parts._replace(query=query).geturl()


OWNER_URL = _raw_url("PONO_TEST_OWNER_URL")
APP_URL = _raw_url("PONO_TEST_APP_URL")
requires_database = pytest.mark.skipif(
    OWNER_URL is None or APP_URL is None, reason="PONO_TEST_OWNER_URL / PONO_TEST_APP_URL not set"
)


@pytest.fixture(scope="session")
def migrated_database() -> Iterator[None]:
    if OWNER_URL is None:
        pytest.skip("no test database")
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", OWNER_URL.replace("%", "%%"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


async def owner_fetch(query: str, *args: object) -> list[asyncpg.Record]:
    assert OWNER_URL is not None
    connection = await asyncpg.connect(OWNER_URL)
    try:
        return list(await connection.fetch(query, *args))
    finally:
        await connection.close()


async def _clean() -> None:
    assert OWNER_URL is not None
    connection = await asyncpg.connect(OWNER_URL)
    try:
        await connection.execute(f"TRUNCATE {', '.join(TABLES_TO_CLEAN)} CASCADE")
    finally:
        await connection.close()


@pytest.fixture
async def clean_database(migrated_database: None) -> AsyncIterator[None]:
    await _clean()
    yield
    await _clean()


class FakeIdentity:
    """A code host that signs in whoever the test names, without any network."""

    def __init__(self) -> None:
        self.next_user: CodeHostUser | None = CodeHostUser("1001", "alice", "alice@example.test")

    def authorization_url(self, state: str, redirect_uri: str) -> str:
        return f"https://code-host.test/authorize?state={state}&redirect_uri={redirect_uri}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        if code == "refused":
            raise IdentityProviderError("refused")
        return f"user-token-for-{code}"

    async def fetch_user(self, user_token: str) -> CodeHostUser:
        assert self.next_user is not None
        return self.next_user


@pytest.fixture
def identity() -> FakeIdentity:
    return FakeIdentity()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        database_app_url=SecretStr(APP_URL) if APP_URL else None,
        public_url="http://console.test",
        allowed_logins=frozenset({"alice", "bob"}),
    )


@pytest.fixture
def world() -> World:
    return make_world()


@pytest.fixture
async def client(
    settings: Settings, identity: FakeIdentity, world: World
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings, identity, world.providers)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://console.test") as http:
        yield http
    engine = app.state.engine
    if engine is not None:
        await engine.dispose()


async def sign_in_as(
    client: httpx.AsyncClient, identity: FakeIdentity, user: CodeHostUser
) -> httpx.Response:
    """Drive the real sign-in flow: login redirect, then callback with the matching state."""

    identity.next_user = user
    # A valid session skips the code host (SC-002): start from a signed-out browser.
    client.cookies.delete("pono_session")
    login = await client.get("/api/v1/auth/login")
    state = parse_qs(urlsplit(login.headers["location"]).query)["state"][0]
    return await client.get("/api/v1/auth/callback", params={"code": "ok", "state": state})
