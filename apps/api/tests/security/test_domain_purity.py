"""T041 — no provider is named in the domain or the application (002 FR-023, constitution III).

Providers live in `infrastructure/`, behind the ports. The only exception is a catalogue of formats
the guards recognize — conventional migration folders and the shape of well-known tokens. Knowing a
format is not calling a provider; the exception is listed here, file by file, so it cannot grow
silently.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.security

SOURCE = Path(__file__).resolve().parents[2] / "src" / "pono_api"
PROVIDERS = re.compile(
    r"github|netlify|coolify|neon|telegram|claude|anthropic|openai|supabase|vercel|drizzle|prisma",
    re.IGNORECASE,
)
FORMAT_CATALOGUES = {
    "application/guards/migrations.py",  # conventional migration folders
    "application/guards/secrets.py",  # shapes of well-known tokens
}


def _named(layer: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted((SOURCE / layer).rglob("*.py")):
        relative = path.relative_to(SOURCE).as_posix()
        names = sorted({m.group(0).lower() for m in PROVIDERS.finditer(path.read_text("utf-8"))})
        if names:
            found[relative] = names
    return found


def test_the_domain_names_no_provider() -> None:
    assert _named("domain") == {}


def test_the_application_names_no_provider_outside_its_format_catalogues() -> None:
    named = _named("application")
    assert set(named) <= FORMAT_CATALOGUES, named
