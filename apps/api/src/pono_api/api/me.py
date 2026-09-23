"""The signed-in person: identity, organization and language (FR-003)."""

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import text

from pono_api.api.dependencies import PrincipalDep, SessionsDep
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import unit_of_work

Locale = Literal["fr", "en"]

router = APIRouter(tags=["me"])


class LocaleChoice(BaseModel):
    locale: Locale


@router.get("/me")
async def read_me(sessions: SessionsDep, principal: PrincipalDep) -> dict[str, object]:
    if not principal.organization_ids:
        raise ApiError("auth.session_required", 401)
    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text("SELECT login, locale FROM people WHERE id = :id"), {"id": principal.person_id}
            )
        ).first()
    if row is None:
        raise ApiError("auth.session_required", 401)
    return {
        "personId": str(principal.person_id),
        "login": row.login,
        "organizationId": str(principal.organization_ids[0]),
        "locale": row.locale,
    }


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


__all__ = ["router"]
