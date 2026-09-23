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

from pono_api.config import Settings, get_settings
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.infrastructure.logging import configure_logging
from pono_api.infrastructure.providers.defaults import default_providers
from pono_api.workers.refresh import refresh_connections, refresh_due_projects

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


async def run_jobs(jobs: Sequence[Job], stop: asyncio.Event) -> None:
    """Run every job on its own cadence until `stop` is set."""

    if not jobs:
        await stop.wait()
        return
    await asyncio.gather(*(_loop(job, stop) for job in jobs))


PROJECTS_TICK = timedelta(minutes=5)
CONNECTIONS_TICK = timedelta(hours=1)


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

    return [
        Job("projects", PROJECTS_TICK, projects),
        Job("connections", CONNECTIONS_TICK, connections),
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
    await run_jobs(jobs, stop)
    logger.info("worker stopped")


def run() -> None:
    configure_logging()
    asyncio.run(main())


__all__ = ["Job", "build_jobs", "run", "run_jobs"]
