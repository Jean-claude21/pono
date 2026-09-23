"""US3 — warned before the quotas give out (FR-024, FR-025, SC-004).

A reading above a threshold raises one alert, visible in the workshop and emailed once; the same
threshold in the same period never raises a second one.
"""

from datetime import date

import httpx
import pytest

from pono_api.config import Settings
from pono_api.domain.quotas import LimitSource, Metric, QuotaReading
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.workers.refresh import read_all_quotas
from tests.conftest import FakeIdentity, owner_fetch, requires_database
from tests.fakes import World
from tests.integration.workshop_setup import LECTIO, connect_everything, stage_lectio

pytestmark = [pytest.mark.integration, requires_database]

SEPTEMBER = date(2026, 9, 1)
OCTOBER = date(2026, 10, 1)


def compute(used: float, period: date = SEPTEMBER) -> QuotaReading:
    return QuotaReading(
        Metric.DB_COMPUTE_SECONDS, used, 360_000, LimitSource.FREE_TIER_ESTIMATE, period
    )


def bandwidth(used: float) -> QuotaReading:
    return QuotaReading(
        Metric.HOSTING_BANDWIDTH_BYTES, used, 100e9, LimitSource.ACCOUNT_PLAN, SEPTEMBER
    )


async def _read(settings: Settings, world: World) -> int:
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        return await read_all_quotas(create_session_factory(engine), world.providers)
    finally:
        await engine.dispose()


async def _lectio(client: httpx.AsyncClient, identity: FakeIdentity, world: World) -> str:
    await connect_everything(client, identity)
    stage_lectio(world)
    project = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()
    return str(project["id"])


async def test_a_quota_above_eighty_percent_warns_once_per_period(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await _lectio(client, identity, world)
    world.factory.database_adapters["neon"].quotas["royal-mouse"] = [compute(300_000)]

    assert await _read(settings, world) == 1
    assert await _read(settings, world) == 0  # same threshold, same period: nothing new

    alerts = await owner_fetch("SELECT threshold, metric, emailed_at FROM alerts")
    assert [(row["threshold"], row["metric"]) for row in alerts] == [(80, "db_compute_seconds")]
    assert alerts[0]["emailed_at"] is not None
    ((recipient, alert),) = world.mailer.sent
    assert recipient.email == "alice@example.test"
    assert (alert.project_name, alert.threshold) == ("lectio-reads", 80)

    await client.post(f"/api/v1/projects/{project_id}/refresh")
    project = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert (project["state"], project["stateReason"]) == ("warning", "quota_warning")
    assert project["quota"]["metric"] == "db_compute_seconds"
    assert project["quota"]["limitSource"] == "free_tier_estimate"
    assert round(project["quota"]["ratio"], 2) == 0.83
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "project.quota_warning"} in workshop["verdicts"]


async def test_ninety_five_percent_raises_a_second_stronger_alert(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await _lectio(client, identity, world)
    neon = world.factory.database_adapters["neon"]
    neon.quotas["royal-mouse"] = [compute(300_000)]
    await _read(settings, world)
    neon.quotas["royal-mouse"] = [compute(350_000)]

    assert await _read(settings, world) == 1

    thresholds = await owner_fetch("SELECT threshold FROM alerts ORDER BY threshold")
    assert [row["threshold"] for row in thresholds] == [80, 95]
    assert [alert.threshold for _, alert in world.mailer.sent] == [80, 95]
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project_id, "code": "project.quota_critical"} in workshop["verdicts"]


async def test_a_new_billing_period_can_warn_again(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await _lectio(client, identity, world)
    neon = world.factory.database_adapters["neon"]
    neon.quotas["royal-mouse"] = [compute(300_000)]
    await _read(settings, world)
    neon.quotas["royal-mouse"] = [compute(300_000, OCTOBER)]

    assert await _read(settings, world) == 1
    readings = await owner_fetch("SELECT period_start FROM quota_readings ORDER BY period_start")
    assert [row["period_start"] for row in readings] == [SEPTEMBER, OCTOBER]


async def test_account_quotas_of_the_host_count_for_its_projects(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    project_id = await _lectio(client, identity, world)
    world.factory.hosting_adapters["netlify"].quotas = [bandwidth(2.7e9)]

    assert await _read(settings, world) == 0
    project = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert [q["metric"] for q in project["quotas"]] == ["hosting_bandwidth_bytes"]
    assert project["quota"]["limitSource"] == "account_plan"
    readings = await owner_fetch("SELECT project_id FROM quota_readings")
    assert [row["project_id"] for row in readings] == [None]


async def test_an_unreachable_mail_server_keeps_the_alert_unsent(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await _lectio(client, identity, world)
    world.factory.database_adapters["neon"].quotas["royal-mouse"] = [compute(340_000)]
    world.mailer.fail = True

    assert await _read(settings, world) == 1
    alerts = await owner_fetch("SELECT emailed_at FROM alerts")
    assert [row["emailed_at"] for row in alerts] == [None]


async def test_without_mail_settings_alerts_stay_in_the_workshop(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await _lectio(client, identity, world)
    world.factory.database_adapters["neon"].quotas["royal-mouse"] = [compute(340_000)]
    world.mailer.configured = False
    world.factory.hosting_adapters["coolify"].unavailable = True

    assert await _read(settings, world) == 1
    assert world.mailer.sent == []
