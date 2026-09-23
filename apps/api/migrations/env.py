"""Alembic environment: migrations always run as the owner role, never as the app role."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from pono_api.config import get_settings
from pono_api.infrastructure.database.session import normalize_asyncpg_url


def _owner_url() -> str:
    configured = context.config.get_main_option("sqlalchemy.url")
    if configured:
        return normalize_asyncpg_url(configured)
    owner_url = get_settings().database_owner_url
    if owner_url is None:
        raise RuntimeError("PONO_DATABASE_OWNER_URL is required to run migrations")
    return normalize_asyncpg_url(owner_url.get_secret_value())


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(_owner_url())
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline migrations are not supported: RLS must be verified online")

asyncio.run(_run_async())
