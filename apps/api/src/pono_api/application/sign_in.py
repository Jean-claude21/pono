"""Sign-in: allow-list check, first-time organization, session issue (FR-006, FR-008, FR-009)."""

from datetime import timedelta
from uuid import uuid7

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.identity import CodeHostUser
from pono_api.application.sessions import IssuedSession, issue_session
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal, unit_of_work


async def _find_person(
    sessions: async_sessionmaker[AsyncSession], user: CodeHostUser
) -> Principal | None:
    async with unit_of_work(sessions, None) as session:
        row = (
            await session.execute(
                text("SELECT person_id, organization_ids FROM pono_find_person(:user_id)"),
                {"user_id": user.user_id},
            )
        ).first()
    if row is None:
        return None
    return Principal(person_id=row.person_id, organization_ids=tuple(row.organization_ids))


async def sign_in(
    sessions: async_sessionmaker[AsyncSession],
    user: CodeHostUser,
    *,
    allowed_logins: frozenset[str],
    session_ttl: timedelta,
) -> tuple[Principal, IssuedSession]:
    """Sign a code host user in; create their personal organization on first sign-in."""

    if user.login.lower() not in allowed_logins:
        raise ApiError("auth.not_allowed", 403)

    principal = await _find_person(sessions, user)
    if principal is None:
        # First sign-in: the person, their personal organization and the owner membership are
        # created in one transaction, under a principal that already names them.
        principal = Principal(person_id=uuid7(), organization_ids=(uuid7(),))
        async with unit_of_work(sessions, principal) as session:
            await session.execute(
                text(
                    "INSERT INTO people (id, code_host_user_id, login, email) "
                    "VALUES (:id, :user_id, :login, :email)"
                ),
                {
                    "id": principal.person_id,
                    "user_id": user.user_id,
                    "login": user.login,
                    "email": user.email,
                },
            )
            await session.execute(
                text("INSERT INTO organizations (id, name) VALUES (:id, :name)"),
                {"id": principal.organization_ids[0], "name": user.login},
            )
            await session.execute(
                text(
                    "INSERT INTO memberships (organization_id, person_id, role) "
                    "VALUES (:organization_id, :person_id, 'owner')"
                ),
                {
                    "organization_id": principal.organization_ids[0],
                    "person_id": principal.person_id,
                },
            )
            issued = await issue_session(session, principal.person_id, session_ttl)
        return principal, issued

    async with unit_of_work(sessions, principal) as session:
        # Keep the login and email current: both can change at the code host.
        await session.execute(
            text(
                "UPDATE people SET login = :login, email = COALESCE(:email, email) WHERE id = :id"
            ),
            {"id": principal.person_id, "login": user.login, "email": user.email},
        )
        issued = await issue_session(session, principal.person_id, session_ttl)
    return principal, issued


__all__ = ["sign_in"]
