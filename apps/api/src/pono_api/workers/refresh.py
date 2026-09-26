"""Scheduled readings (FR-013, FR-022, research R-09).

The worker learns the organizations through one SECURITY DEFINER lookup, then works inside each
one under its own row-level security context, exactly as a request would.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connections import refresh_connection_statuses
from pono_api.application.quotas import read_quotas
from pono_api.application.refresh_project import Providers, refresh_project
from pono_api.application.releases import sync_all_releases
from pono_api.application.rollback import settle_rollbacks
from pono_api.application.rollback_requests import expire_rollback_requests
from pono_api.application.runtime_writes import save_due
from pono_api.application.runtimes import follow_runtimes
from pono_api.domain.projects import REFRESH_INTERVAL
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.worker.refresh")

# A project is due a little before its 15 minutes, so a tick every few minutes never lets one wait
# longer than the interval.
DUE_MARGIN = timedelta(minutes=3)


async def organizations(sessions: async_sessionmaker[AsyncSession]) -> list[UUID]:
    async with unit_of_work(sessions, None) as session:
        rows = await session.execute(text("SELECT pono_worker_organizations()"))
        return [row[0] for row in rows]


async def due_projects(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, now: datetime
) -> list[UUID]:
    async with unit_of_work(sessions, principal) as session:
        rows = await session.execute(
            text(
                "SELECT id FROM projects "
                "WHERE refreshed_at IS NULL OR stale OR refreshed_at <= :due "
                "ORDER BY refreshed_at NULLS FIRST"
            ),
            {"due": now - (REFRESH_INTERVAL - DUE_MARGIN)},
        )
        return [row.id for row in rows]


async def refresh_due_projects(
    sessions: async_sessionmaker[AsyncSession],
    providers: Providers,
    now: datetime | None = None,
) -> int:
    """Read every project whose last reading is older than the interval; returns how many."""

    moment = now or datetime.now(UTC)
    count = 0
    for organization_id in await organizations(sessions):
        principal = Principal.for_organization(organization_id)
        for project_id in await due_projects(sessions, principal, moment):
            try:
                await refresh_project(sessions, principal, project_id, providers)
                count += 1
            except Exception:  # one project never blocks the others
                logger.exception("reading of project %s failed", project_id)
    return count


async def read_all_quotas(sessions: async_sessionmaker[AsyncSession], providers: Providers) -> int:
    """Quota readings of every organization; returns how many alerts were raised."""

    raised = 0
    for organization_id in await organizations(sessions):
        try:
            raised += await read_quotas(
                sessions, Principal.for_organization(organization_id), providers
            )
        except Exception:
            logger.exception("quota reading of organization %s failed", organization_id)
    return raised


async def read_all_releases(
    sessions: async_sessionmaker[AsyncSession], providers: Providers
) -> None:
    """Release attempts of every organization, the rollbacks in progress (002), and agents'
    rollback requests nobody handled (003)."""

    for organization_id in await organizations(sessions):
        try:
            principal = Principal.for_organization(organization_id)
            await sync_all_releases(sessions, providers, organization_id)
            await settle_rollbacks(sessions, principal, providers)
            await expire_rollback_requests(sessions, principal)
        except Exception:
            logger.exception("release reading of organization %s failed", organization_id)


async def follow_all_runtimes(
    sessions: async_sessionmaker[AsyncSession], providers: Providers
) -> None:
    """Every runtime of every organization: proposal, host, gate, database; then the writes a
    quiet minute old are saved to the development branch (004)."""

    for organization_id in await organizations(sessions):
        try:
            principal = Principal.for_organization(organization_id)
            await follow_runtimes(sessions, principal, providers)
            await save_due(sessions, principal, providers)
        except Exception:
            logger.exception("runtime reading of organization %s failed", organization_id)


async def refresh_connections(
    sessions: async_sessionmaker[AsyncSession], providers: Providers
) -> None:
    for organization_id in await organizations(sessions):
        try:
            await refresh_connection_statuses(
                sessions,
                Principal.for_organization(organization_id),
                providers.code_host,
                providers.factory,
            )
        except Exception:
            logger.exception("connection check of organization %s failed", organization_id)


__all__ = [
    "due_projects",
    "follow_all_runtimes",
    "organizations",
    "read_all_quotas",
    "read_all_releases",
    "refresh_connections",
    "refresh_due_projects",
]
