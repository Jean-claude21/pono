"""Linking the chat where a person's quota alerts go (FR-025, D-015, research R-10b).

The person asks for a link, starts the chat, then confirms. The link carries a one-time code
valid 15 minutes; only its digest is stored. Everything happens on the person's own row.
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.ports import ChatMessenger, ChatRecipient, ProviderUnavailableError
from pono_api.application.sessions import hash_token
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal, unit_of_work

LINK_TTL = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class ChatLink:
    url: str
    expires_at: datetime


def _configured(messenger: ChatMessenger | None) -> ChatMessenger:
    if messenger is None or not messenger.configured:
        raise ApiError("service.chat_unconfigured", 503)
    return messenger


async def start_chat_link(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    messenger: ChatMessenger | None,
) -> ChatLink:
    chat = _configured(messenger)
    code = secrets.token_urlsafe(18)
    try:
        url = await chat.link_url(code)
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    expires_at = datetime.now(UTC) + LINK_TTL
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE people SET chat_link_digest = :digest, chat_link_expires_at = :expires "
                "WHERE id = :id"
            ),
            {"digest": hash_token(code), "expires": expires_at, "id": principal.person_id},
        )
    # The code goes back to the person inside the link only; it is never stored in clear.
    return ChatLink(url=url, expires_at=expires_at)


async def confirm_chat_link(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    messenger: ChatMessenger | None,
) -> None:
    """Finds the chat started with the pending code: only digests are compared."""

    chat = _configured(messenger)
    async with unit_of_work(sessions, principal) as session:
        pending = (
            await session.execute(
                text(
                    "SELECT locale, chat_link_digest FROM people WHERE id = :id "
                    "AND chat_link_digest IS NOT NULL AND chat_link_expires_at > now()"
                ),
                {"id": principal.person_id},
            )
        ).first()
    if pending is None:
        raise ApiError("chat.link_expired", 409)
    try:
        starts = await chat.started_chats()
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    digest = bytes(pending.chat_link_digest)
    chat_id = next(
        (
            start.chat_id
            for start in reversed(starts)
            if hmac.compare_digest(hash_token(start.code), digest)
        ),
        None,
    )
    if chat_id is None:
        raise ApiError("chat.link_not_found", 409)
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE people SET chat_id = :chat_id, chat_link_digest = NULL, "
                "chat_link_expires_at = NULL WHERE id = :id"
            ),
            {"chat_id": chat_id, "id": principal.person_id},
        )
    try:
        await chat.send_linked(ChatRecipient(chat_id=chat_id, locale=pending.locale))
    except ProviderUnavailableError:
        pass  # the link holds; the confirmation message is a courtesy


async def unlink_chat(sessions: async_sessionmaker[AsyncSession], principal: Principal) -> None:
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE people SET chat_id = NULL, chat_link_digest = NULL, "
                "chat_link_expires_at = NULL WHERE id = :id"
            ),
            {"id": principal.person_id},
        )


__all__ = ["LINK_TTL", "ChatLink", "confirm_chat_link", "start_chat_link", "unlink_chat"]
