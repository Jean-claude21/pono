"""T091 — quota alerts by a chat the person links themselves (FR-025, D-015, research R-10b)."""

from datetime import date

import httpx
import pytest

from pono_api.config import Settings
from pono_api.domain.quotas import LimitSource, Metric, QuotaReading
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.workers.refresh import read_all_quotas
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World
from tests.integration.workshop_setup import ALICE, BOB, LECTIO, connect_everything, stage_lectio

pytestmark = [pytest.mark.integration, requires_database]


async def _link(client: httpx.AsyncClient, world: World, chat_id: str = "4242") -> httpx.Response:
    link = (await client.post("/api/v1/me/chat-link")).json()
    world.messenger.start(link["url"], chat_id)
    return await client.post("/api/v1/me/chat-link/confirm")


async def test_the_person_links_a_chat_with_a_one_time_code(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    assert (await client.get("/api/v1/me")).json()["chatLinked"] is False

    link = await client.post("/api/v1/me/chat-link")
    code = link.json()["url"].rsplit("=", 1)[1]
    early = await client.post("/api/v1/me/chat-link/confirm")
    world.messenger.start(link.json()["url"], "4242")
    confirmed = await client.post("/api/v1/me/chat-link/confirm")

    assert early.json() == {"error": {"code": "chat.link_not_found"}}
    assert confirmed.status_code == 204
    assert (await client.get("/api/v1/me")).json()["chatLinked"] is True
    assert [recipient.chat_id for recipient in world.messenger.linked] == ["4242"]
    people = await owner_fetch("SELECT chat_id, chat_link_digest FROM people")
    assert [(row["chat_id"], row["chat_link_digest"]) for row in people] == [("4242", None)]
    assert all(code not in str(row) for row in people)  # only a digest was ever stored

    again = await client.post("/api/v1/me/chat-link/confirm")
    assert again.json() == {"error": {"code": "chat.link_expired"}}


async def test_a_code_started_by_someone_else_links_nothing(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, BOB)
    bob_link = (await client.post("/api/v1/me/chat-link")).json()
    await sign_in_as(client, identity, ALICE)
    await client.post("/api/v1/me/chat-link")
    world.messenger.start(bob_link["url"], "9999")  # Bob's code, not Alice's

    refused = await client.post("/api/v1/me/chat-link/confirm")

    assert refused.json() == {"error": {"code": "chat.link_not_found"}}
    assert (await client.get("/api/v1/me")).json()["chatLinked"] is False


async def test_an_expired_code_must_be_asked_again(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    link = (await client.post("/api/v1/me/chat-link")).json()
    world.messenger.start(link["url"], "4242")
    await owner_fetch("UPDATE people SET chat_link_expires_at = now() - interval '1 minute'")

    expired = await client.post("/api/v1/me/chat-link/confirm")

    assert expired.json() == {"error": {"code": "chat.link_expired"}}


async def test_without_a_bot_the_service_says_so(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    world.messenger.configured = False

    refused = await client.post("/api/v1/me/chat-link")

    assert refused.status_code == 503
    assert refused.json() == {"error": {"code": "service.chat_unconfigured"}}


async def test_an_unreachable_chat_keeps_the_link_pending(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await sign_in_as(client, identity, ALICE)
    link = (await client.post("/api/v1/me/chat-link")).json()
    world.messenger.start(link["url"], "4242")
    world.messenger.fail = True

    failed = await client.post("/api/v1/me/chat-link/confirm")
    world.messenger.fail = False
    retried = await client.post("/api/v1/me/chat-link/confirm")

    assert failed.json() == {"error": {"code": "provider.unavailable"}}
    assert retried.status_code == 204


async def test_alerts_reach_the_linked_chat_once_and_stop_when_unlinked(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    await client.post("/api/v1/projects", json={"repository": LECTIO})
    assert (await _link(client, world)).status_code == 204
    quotas = world.factory.database_adapters["neon"].quotas
    quotas["royal-mouse"] = [
        QuotaReading(
            Metric.DB_COMPUTE_SECONDS,
            300_000,
            360_000,
            LimitSource.FREE_TIER_ESTIMATE,
            date(2026, 9, 1),
        )
    ]

    assert await _read(settings, world) == 1
    assert await _read(settings, world) == 0

    ((recipient, alert),) = world.messenger.sent
    assert (recipient.chat_id, alert.project_name, alert.threshold) == ("4242", "lectio-reads", 80)
    alerts = await owner_fetch("SELECT chat_sent_at FROM alerts")
    assert alerts[0]["chat_sent_at"] is not None

    assert (await client.delete("/api/v1/me/chat")).status_code == 204
    assert (await client.get("/api/v1/me")).json()["chatLinked"] is False
    quotas["royal-mouse"][0] = QuotaReading(
        Metric.DB_COMPUTE_SECONDS,
        350_000,
        360_000,
        LimitSource.FREE_TIER_ESTIMATE,
        date(2026, 9, 1),
    )
    assert await _read(settings, world) == 1  # the 95 % alert is raised...
    assert len(world.messenger.sent) == 1  # ...but no longer sent to the unlinked chat


async def test_a_chat_failure_never_holds_the_email_back(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    world: World,
    settings: Settings,
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    await client.post("/api/v1/projects", json={"repository": LECTIO})
    await _link(client, world)
    world.messenger.fail = True
    world.factory.database_adapters["neon"].quotas["royal-mouse"] = [
        QuotaReading(
            Metric.DB_COMPUTE_SECONDS,
            300_000,
            360_000,
            LimitSource.FREE_TIER_ESTIMATE,
            date(2026, 9, 1),
        )
    ]

    assert await _read(settings, world) == 1

    alerts = await owner_fetch("SELECT emailed_at, chat_sent_at FROM alerts")
    assert alerts[0]["emailed_at"] is not None
    assert alerts[0]["chat_sent_at"] is None
    assert len(world.mailer.sent) == 1


async def _read(settings: Settings, world: World) -> int:
    assert settings.database_app_url is not None
    engine = create_engine(settings.database_app_url)
    try:
        return await read_all_quotas(create_session_factory(engine), world.providers)
    finally:
        await engine.dispose()
