"""Alerts over a Telegram bot (D-015, research R-10b). Plain HTTP, no SDK.

The bot token lives in the service configuration only; every request path carries it, so a
failure is re-raised without the underlying error, whose text may hold the URL.
Without a token the messenger is unconfigured: alerts stay in the workshop and the health probe
says chat is not configured.
"""

from typing import cast

import httpx
from pydantic import SecretStr

from pono_api.application.ports import (
    ChatRecipient,
    ChatStart,
    ProviderUnavailableError,
    RaisedAlert,
)
from pono_api.infrastructure.mailer import METRIC_NAMES, SOURCES

API_URL = "https://api.telegram.org"

JsonObject = dict[str, object]


def _locale(value: str | None) -> str:
    return value if value in ("fr", "en") else "fr"


def alert_text(recipient: ChatRecipient, alert: RaisedAlert) -> str:
    """The alert in the recipient's language; French when they never chose one."""

    locale = _locale(recipient.locale)
    metric = METRIC_NAMES[locale].get(alert.metric, alert.metric)
    source = SOURCES[locale].get(alert.limit_source, alert.limit_source)
    percent = round(alert.used / alert.limit * 100) if alert.limit else alert.threshold
    target = alert.project_name or metric
    if locale == "fr":
        return (
            f"Pono · {target} : {metric} à {percent} %\n\n"
            f"Le quota a dépassé {alert.threshold} % de {source}. "
            "Au-delà de la limite, le fournisseur peut mettre le service en pause. "
            "Le détail est dans ton atelier Pono."
        )
    return (
        f"Pono · {target}: {metric} at {percent}%\n\n"
        f"The quota passed {alert.threshold}% of {source}. "
        "Beyond the limit, the provider may pause the service. "
        "The detail is in your Pono workshop."
    )


def linked_text(recipient: ChatRecipient) -> str:
    if _locale(recipient.locale) == "fr":
        return "Pono est relié à cette conversation : tes alertes de quota arriveront ici."
    return "Pono is linked to this chat: your quota alerts will arrive here."


class TelegramMessenger:
    def __init__(
        self,
        token: SecretStr | None,
        *,
        api_url: str = API_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._transport = transport
        self._username: str | None = None

    @property
    def configured(self) -> bool:
        return self._token is not None

    async def link_url(self, code: str) -> str:
        if self._username is None:
            me = await self._call("getMe")
            self._username = str(cast(JsonObject, me)["username"])
        return f"https://t.me/{self._username}?start={code}"

    async def started_chats(self) -> list[ChatStart]:
        # Updates stay available for 24 hours; they are never acknowledged here, so a pending
        # link of another person is never lost (research R-10b).
        updates = await self._call("getUpdates", {"allowed_updates": ["message"]})
        starts: list[ChatStart] = []
        for update in cast(list[JsonObject], updates):
            message = update.get("message")
            if not isinstance(message, dict):
                continue
            chat, words = message.get("chat"), str(message.get("text") or "").split()
            if (
                len(words) == 2
                and words[0] == "/start"
                and isinstance(chat, dict)
                and chat.get("type") == "private"
            ):
                starts.append(ChatStart(code=words[1], chat_id=str(chat["id"])))
        return starts

    async def send_linked(self, recipient: ChatRecipient) -> None:
        await self._send(recipient.chat_id, linked_text(recipient))

    async def send_alert(self, recipient: ChatRecipient, alert: RaisedAlert) -> None:
        await self._send(recipient.chat_id, alert_text(recipient, alert))

    async def _send(self, chat_id: str, text: str) -> None:
        await self._call("sendMessage", {"chat_id": chat_id, "text": text})

    async def _call(self, method: str, payload: JsonObject | None = None) -> object:
        if self._token is None:
            raise ProviderUnavailableError("chat is not configured")
        url = f"{self._api_url}/bot{self._token.get_secret_value()}/{method}"
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=20) as client:
                response = await client.post(url, json=payload or {})
            body = response.json()
        except httpx.HTTPError, ValueError:
            raise ProviderUnavailableError(f"chat {method} failed") from None
        if not isinstance(body, dict) or body.get("ok") is not True:
            raise ProviderUnavailableError(f"chat {method} answered {response.status_code}")
        return body.get("result")


__all__ = ["TelegramMessenger", "alert_text", "linked_text"]
