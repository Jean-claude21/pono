"""Container probe for both roles of the one image (no curl in the slim image).

The service answers on /api/v1/health; the worker opens no port, so it proves it is alive by
touching a heartbeat file every minute.
"""

import os
import sys
import time
import urllib.request
from pathlib import Path

HEARTBEAT = Path(os.environ.get("PONO_HEARTBEAT_FILE", "/tmp/pono-worker.alive"))  # noqa: S108
HEARTBEAT_MAX_AGE_SECONDS = 180


def worker_alive(heartbeat: Path = HEARTBEAT, now: float | None = None) -> bool:
    try:
        age = (now or time.time()) - heartbeat.stat().st_mtime
    except FileNotFoundError:
        return False
    return age < HEARTBEAT_MAX_AGE_SECONDS


def service_alive(url: str = "http://127.0.0.1:8000/api/v1/health") -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310 - fixed local URL
            return bool(response.status == 200)
    except OSError:
        return False


def main() -> None:
    alive = worker_alive() if os.environ.get("PONO_ROLE") == "worker" else service_alive()
    sys.exit(0 if alive else 1)


__all__ = ["HEARTBEAT", "main", "service_alive", "worker_alive"]
