"""Quota readers and the alert email, against the payloads the providers really return (T055)."""

import smtplib
from datetime import date
from email.message import EmailMessage
from typing import ClassVar

import pytest
from pydantic import SecretStr

from pono_api.application.ports import RaisedAlert, Recipient
from pono_api.domain.quotas import LimitSource, Metric
from pono_api.infrastructure.mailer import SmtpMailer, compose
from pono_api.infrastructure.providers.coolify import CoolifyHosting
from pono_api.infrastructure.providers.neon import (
    FREE_COMPUTE_SECONDS,
    FREE_TRANSFER_BYTES,
    NeonDatabase,
)
from pono_api.infrastructure.providers.netlify import NetlifyHosting
from tests.unit.test_providers import Api

pytestmark = pytest.mark.unit

LECTIO_PROJECT = {
    "project": {
        "id": "royal-mouse",
        "org_id": "org-a",
        "compute_time_seconds": 7561,
        "data_transfer_bytes": 203372,
        "synthetic_storage_size": 31875072,
        "branch_logical_size_limit_bytes": 536870912,
        "consumption_period_start": "2026-09-01T00:00:00Z",
        "consumption_period_end": "2026-10-01T00:00:00Z",
    }
}


async def test_netlify_reads_the_account_bandwidth_against_its_plan() -> None:
    api = Api(
        {
            "/api/v1/accounts": [{"slug": "jean-claude21"}],
            "/api/v1/accounts/jean-claude21/bandwidth": {
                "used": 2733676870,
                "included": 107374182400,
                "period_start_date": "2026-09-01T00:00:00.000-07:00",
                "period_end_date": "2026-10-01T00:00:00.000-07:00",
            },
        }
    )
    (reading,) = await NetlifyHosting("k", lambda _: None, transport=api.transport).read_quotas()

    assert reading.metric is Metric.HOSTING_BANDWIDTH_BYTES
    assert (reading.used, reading.limit) == (2733676870, 107374182400)
    assert reading.limit_source is LimitSource.ACCOUNT_PLAN
    assert (reading.period_start, reading.period_end) == (date(2026, 9, 1), date(2026, 10, 1))


async def test_netlify_without_usage_reports_nothing() -> None:
    api = Api({"/api/v1/accounts": [{"slug": "x"}], "/api/v1/accounts/x/bandwidth": {}})
    assert await NetlifyHosting("k", lambda _: None, transport=api.transport).read_quotas() == []


async def test_a_server_of_ones_own_has_no_quota() -> None:
    hosting = CoolifyHosting("https://c.test", "k", lambda _: None, transport=Api({}).transport)
    assert await hosting.read_quotas() == []


@pytest.mark.parametrize(("plan", "free"), [("free", True), ("launch", False)])
async def test_neon_reads_compute_storage_and_transfer(plan: str, free: bool) -> None:
    api = Api(
        {
            "/api/v2/projects/royal-mouse": LECTIO_PROJECT,
            "/api/v2/organizations/org-a": {"plan": plan},
        }
    )
    database = NeonDatabase(
        "k", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )

    readings = {reading.metric: reading for reading in await database.read_quotas("royal-mouse")}

    compute = readings[Metric.DB_COMPUTE_SECONDS]
    storage = readings[Metric.DB_STORAGE_BYTES]
    transfer = readings[Metric.DB_TRANSFER_BYTES]
    assert compute.used == 7561
    assert compute.limit == (FREE_COMPUTE_SECONDS if free else None)
    assert compute.limit_source is LimitSource.FREE_TIER_ESTIMATE
    # The storage limit is stated by the provider: it is the account's plan, not an estimate.
    assert (storage.limit, storage.limit_source) == (536870912, LimitSource.ACCOUNT_PLAN)
    assert transfer.limit == (FREE_TRANSFER_BYTES if free else None)
    assert compute.period_start == date(2026, 9, 1)


async def test_neon_personal_projects_use_the_personal_plan() -> None:
    project = {"project": {**LECTIO_PROJECT["project"], "org_id": None}}
    api = Api({"/api/v2/projects/p": project, "/api/v2/users/me": {"plan": "free_v2"}})
    database = NeonDatabase(
        "k", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )
    readings = await database.read_quotas("p")
    assert {r.metric: r.limit for r in readings}[Metric.DB_COMPUTE_SECONDS] == FREE_COMPUTE_SECONDS


async def test_neon_without_a_period_reports_nothing() -> None:
    api = Api({"/api/v2/projects/p": {"project": {"id": "p"}}})
    database = NeonDatabase(
        "k", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )
    assert await database.read_quotas("p") == []


ALERT = RaisedAlert(
    project_name="lectio-reads",
    metric="db_compute_seconds",
    threshold=80,
    used=300_000,
    limit=360_000,
    limit_source="free_tier_estimate",
)


@pytest.mark.parametrize(
    ("locale", "subject", "phrase"),
    [
        ("fr", "Pono · lectio-reads : temps de calcul de la base à 83 %", "l'offre gratuite"),
        (None, "Pono · lectio-reads : temps de calcul de la base à 83 %", "a dépassé 80 %"),
        ("en", "Pono · lectio-reads: database compute time at 83%", "the free tier"),
    ],
)
def test_the_alert_email_speaks_the_recipient_language(
    locale: str | None, subject: str, phrase: str
) -> None:
    message = compose(Recipient("alice@example.test", locale), ALERT, "pono@example.test")
    assert message["Subject"] == subject
    assert message["To"] == "alice@example.test"
    assert phrase in message.get_content()


class FakeSmtp:
    sent: ClassVar[list[EmailMessage]] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.logged_in = False

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        assert (username, password) == ("pono", "secret")

    def send_message(self, message: EmailMessage) -> None:
        FakeSmtp.sent.append(message)


async def test_smtp_mailer_sends_only_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    FakeSmtp.sent = []
    recipient = Recipient("alice@example.test", "en")

    await SmtpMailer(None, 587, None, None, None).send_alert(recipient, ALERT)
    assert FakeSmtp.sent == []

    mailer = SmtpMailer("smtp.test", 587, "pono", SecretStr("secret"), "pono@example.test")
    assert mailer.configured
    await mailer.send_alert(recipient, ALERT)
    assert [message["To"] for message in FakeSmtp.sent] == ["alice@example.test"]
