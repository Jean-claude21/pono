"""The container probe knows both roles of the one image."""

import asyncio
import os
import time
from pathlib import Path

import pytest

from pono_api import healthcheck
from pono_api.workers.runner import run_jobs

pytestmark = pytest.mark.unit


def test_a_fresh_heartbeat_means_the_worker_is_alive(tmp_path: Path) -> None:
    heartbeat = tmp_path / "alive"
    assert healthcheck.worker_alive(heartbeat) is False
    heartbeat.touch()
    assert healthcheck.worker_alive(heartbeat) is True
    old = time.time() - 600
    os.utime(heartbeat, (old, old))
    assert healthcheck.worker_alive(heartbeat) is False


def test_the_service_probe_fails_without_a_service() -> None:
    assert healthcheck.service_alive("http://127.0.0.1:9/api/v1/health") is False


def test_main_exits_by_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PONO_ROLE", "worker")
    monkeypatch.setattr(healthcheck, "worker_alive", lambda: True)
    with pytest.raises(SystemExit) as worker:
        healthcheck.main()
    monkeypatch.delenv("PONO_ROLE")
    monkeypatch.setattr(healthcheck, "service_alive", lambda: False)
    with pytest.raises(SystemExit) as service:
        healthcheck.main()
    assert (worker.value.code, service.value.code) == (0, 1)


async def test_the_worker_beats_while_it_runs(tmp_path: Path) -> None:
    heartbeat = tmp_path / "alive"
    stop = asyncio.Event()
    running = asyncio.create_task(run_jobs([], stop, heartbeat))
    for _ in range(50):
        if heartbeat.exists():
            break
        await asyncio.sleep(0.01)
    stop.set()
    await running
    assert heartbeat.exists()
