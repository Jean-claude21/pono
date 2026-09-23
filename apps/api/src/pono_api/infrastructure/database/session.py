"""Async database resources without global mutable sessions (ported from KYA-Platform)."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def normalize_asyncpg_url(database_url: str) -> str:
    """Translate a standard Postgres URL into the form asyncpg accepts."""

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("database URL must use PostgreSQL")

    ssl_mode: str | None = None
    query: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key == "channel_binding":
            continue
        if key == "sslmode":
            ssl_mode = value
            continue
        query.append((key, value))

    if ssl_mode is not None and not any(key == "ssl" for key, _ in query):
        query.append(("ssl", ssl_mode))

    return urlunsplit(
        ("postgresql+asyncpg", parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def create_engine(database_url: SecretStr) -> AsyncEngine:
    """Create a bounded, liveness-checked runtime engine."""

    return create_async_engine(
        normalize_asyncpg_url(database_url.get_secret_value()),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=300,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create request-scoped sessions; one session serves one task."""

    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


__all__ = ["create_engine", "create_session_factory", "normalize_asyncpg_url"]
