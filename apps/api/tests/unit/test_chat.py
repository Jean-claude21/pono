"""T090 — alerts over a chat bot (D-015, research R-10b), against a mocked transport."""

import json

import httpx
import pytest
from pydantic import SecretStr

from pono_api.application.ports import (
    ChatRecipient,
    ChatStart,
    ProviderUnavailableError,
    RaisedAlert,
)
from pono_api.infrastructure.chat import TelegramMessenger, alert_text

TOKEN = "123456789:" + "AAbbCC_dd-" * 4
ALERT = RaisedAlert(
    project_name="lectio-reads",
    metric="db_compute_seconds",
    threshold=80,
    used=300_000,
    limit=360_000,
    limit_source="free_tier_estimate",
)


def _update(update_id: int, text: str, chat_id: int, kind: str = "private") -> dict[str, object]:
    return {
        "update_id": update_id,
        "message": {"text": text, "chat": {"id": chat_id, "type": kind}},
    }


class Bot:
    """A bot endpoint that records every call and answers like the real one."""

    def __init__(self, updates: list[dict[str, object]] | None = None) -> None:
        self.updates = updates or []
        self.calls: list[tuple[str, dict[str, object]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.url.path.startswith(f"/bot{TOKEN}/")
        method = request.url.path.rsplit("/", 1)[1]
        payload = json.loads(request.content or b"{}")
        self.calls.append((method, payload))
        results: dict[str, object] = {
            "getMe": {"id": 1, "is_bot": True, "username": "pono_alerts_bot"},
            "getUpdates": self.updates,
            "sendMessage": {"message_id": 7},
        }
        return httpx.Response(200, json={"ok": True, "result": results[method]})


def _messenger(bot: Bot) -> TelegramMessenger:
    return TelegramMessenger(SecretStr(TOKEN), transport=httpx.MockTransport(bot))


async def test_the_link_opens_the_bot_with_the_code() -> None:
    bot = Bot()
    messenger = _messenger(bot)

    assert await messenger.link_url("abc_123") == "https://t.me/pono_alerts_bot?start=abc_123"
    await messenger.link_url("other")
    assert [method for method, _ in bot.calls] == ["getMe"]  # the bot name is asked once


async def test_only_private_chats_started_with_a_code_are_returned() -> None:
    bot = Bot(
        [
            _update(1, "hello", 11),
            _update(2, "/start abc_123", 22, kind="group"),
            _update(3, "/start abc_123", 33),
            _update(4, "/start", 44),
            {"update_id": 5, "edited_message": {"text": "/start x"}},
        ]
    )
    messenger = _messenger(bot)

    assert await messenger.started_chats() == [ChatStart(code="abc_123", chat_id="33")]
    assert all("offset" not in payload for _, payload in bot.calls)  # never acknowledged


async def test_an_alert_is_written_in_the_recipient_language() -> None:
    bot = Bot()
    messenger = _messenger(bot)

    await messenger.send_alert(ChatRecipient(chat_id="33", locale="en"), ALERT)

    ((method, payload),) = bot.calls
    assert method == "sendMessage"
    assert payload["chat_id"] == "33"
    assert "database compute time at 83%" in str(payload["text"])
    french = alert_text(ChatRecipient(chat_id="33", locale=None), ALERT)
    assert "temps de calcul de la base à 83 %" in french


async def test_a_refusal_or_an_outage_never_carries_the_token() -> None:
    refused = httpx.MockTransport(
        lambda _: httpx.Response(401, json={"ok": False, "description": "Unauthorized"})
    )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}")

    for transport in (refused, httpx.MockTransport(unreachable)):
        messenger = TelegramMessenger(SecretStr(TOKEN), transport=transport)
        with pytest.raises(ProviderUnavailableError) as raised:
            await messenger.send_alert(ChatRecipient(chat_id="33", locale="fr"), ALERT)
        assert TOKEN not in str(raised.value)
        assert raised.value.__cause__ is None


def test_without_a_token_the_messenger_is_unconfigured() -> None:
    assert TelegramMessenger(None).configured is False
    assert TelegramMessenger(SecretStr(TOKEN)).configured is True
