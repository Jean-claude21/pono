"""The signed-in person: identity, organization, language (FR-003) and alert address (FR-025)."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from pono_api.api.dependencies import PrincipalDep, SessionsDep, SettingsDep
from pono_api.api.schemas import Me
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import unit_of_work

Locale = Literal["fr", "en"]

router = APIRouter(tags=["me"])


class LocaleChoice(BaseModel):
    locale: Locale


class AlertAddress(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)


@router.get("/me")
async def read_me(sessions: SessionsDep, principal: PrincipalDep, settings: SettingsDep) -> Me:
    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text("SELECT login, locale, email FROM people WHERE id = :id"),
                {"id": principal.person_id},
            )
        ).first()
    if row is None:
        raise ApiError("auth.session_required", 401)
    return Me(
        person_id=principal.person_id,
        login=row.login,
        organization_id=principal.organization_id,
        locale=row.locale,
        email=row.email,
        alert_emails_enabled=settings.smtp_configured,
        code_host_install_url=settings.code_host_install_url,
    )


@router.put("/me/locale", status_code=204)
async def choose_locale(
    choice: LocaleChoice, sessions: SessionsDep, principal: PrincipalDep
) -> Response:
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text("UPDATE people SET locale = :locale WHERE id = :id"),
            {"locale": choice.locale, "id": principal.person_id},
        )
    return Response(status_code=204)


@router.put("/me/email", status_code=204)
async def choose_alert_address(
    choice: AlertAddress, sessions: SessionsDep, principal: PrincipalDep
) -> Response:
    """Where quota alerts go when the code host keeps the person's address private (FR-025)."""

    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text("UPDATE people SET email = :email WHERE id = :id"),
            {"email": choice.email, "id": principal.person_id},
        )
    return Response(status_code=204)


__all__ = ["router"]
