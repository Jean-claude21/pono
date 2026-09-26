"""Background worker: runs scheduled jobs until asked to stop (research R-09).

Each job owns its cadence. A failing run is logged and retried at the next tick; it never stops
the other jobs. Jobs are registered by the phases that need them.
"""

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from pono_api.config import Settings, get_settings
from pono_api.domain.releases import RELEASES_INTERVAL
from pono_api.healthcheck import HEARTBEAT
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.infrastructure.logging import configure_logging
from pono_api.infrastructure.providers.defaults import default_providers
from pono_api.workers.refresh import (
    follow_all_runtimes,
    read_all_quotas,
    read_all_releases,
    refresh_connections,
    refresh_due_projects,
)

logger = logging.getLogger("pono.worker")


@dataclass(frozen=True, slots=True)
class Job:
    name: str
    interval: timedelta
    run: Callable[[], Awaitable[None]]


async def _loop(job: Job, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await job.run()
        except Exception:
            logger.exception("job %s failed; retrying at the next tick", job.name)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=job.interval.total_seconds())


HEARTBEAT_INTERVAL = timedelta(minutes=1)


async def _heartbeat(stop: asyncio.Event, heartbeat: Path) -> None:
    """Touch the heartbeat file the container probe reads (the worker opens no port)."""

    while not stop.is_set():
        await asyncio.to_thread(heartbeat.touch)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL.total_seconds())


async def run_jobs(jobs: Sequence[Job], stop: asyncio.Event, heartbeat: Path | None = None) -> None:
    """Run every job on its own cadence until `stop` is set."""

    beating = [_heartbeat(stop, heartbeat)] if heartbeat is not None else []
    if not jobs:
        await asyncio.gather(stop.wait(), *beating)
        return
    await asyncio.gather(*(_loop(job, stop) for job in jobs), *beating)


PROJECTS_TICK = timedelta(minutes=5)
CONNECTIONS_TICK = timedelta(hours=1)
QUOTAS_TICK = timedelta(hours=1)
RUNTIMES_TICK = timedelta(seconds=15)


def build_jobs(settings: Settings) -> list[Job]:
    """Jobs registered for this deployment. Phase-specific jobs are added here."""

    if settings.database_app_url is None:
        logger.warning("no database configured: the worker has nothing to do")
        return []
    sessions = create_session_factory(create_engine(settings.database_app_url))
    providers = default_providers(settings)

    async def projects() -> None:
        count = await refresh_due_projects(sessions, providers)
        logger.info("read %d project(s)", count)

    async def connections() -> None:
        await refresh_connections(sessions, providers)

    async def quotas() -> None:
        raised = await read_all_quotas(sessions, providers)
        logger.info("quota readings raised %d alert(s)", raised)

    async def releases() -> None:
        await read_all_releases(sessions, providers)

    async def runtimes() -> None:
        await follow_all_runtimes(sessions, providers)

    return [
        Job("projects", PROJECTS_TICK, projects),
        Job("connections", CONNECTIONS_TICK, connections),
        Job("quotas", QUOTAS_TICK, quotas),
        Job("releases", RELEASES_INTERVAL, releases),
        Job("runtimes", RUNTIMES_TICK, runtimes),
    ]


def _install_stop_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        # Windows event loops do not support signal handlers; Ctrl+C still interrupts there.
        with contextlib.suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(signum, stop.set)


async def main() -> None:
    stop = asyncio.Event()
    _install_stop_handlers(stop)
    jobs = build_jobs(get_settings())
    logger.info("worker started with %d job(s)", len(jobs))
    await run_jobs(jobs, stop, HEARTBEAT)
    logger.info("worker stopped")


def run() -> None:
    configure_logging()
    asyncio.run(main())


__all__ = ["Job", "build_jobs", "run", "run_jobs"]
