"""The production branch protection (002 US3, FR-013 to FR-015, research R-07).

Read at import and at every project reading; applied by Pono on a person's click. A change of state
is written to the journal, so a protection removed at the code host never goes unnoticed.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.ports import ProtectionRefusedError, ProviderUnavailableError
from pono_api.application.protection_state import store_protection
from pono_api.application.refresh_project import Providers
from pono_api.application.releases import load_release_projects
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work


async def apply_protection(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
) -> dict[str, object]:
    projects = await load_release_projects(sessions, principal, project_id)
    if not projects:
        raise not_found("project")
    (project,) = projects
    if project.branch is None:
        raise ApiError("protection.no_production_branch", 422)
    code_host = providers.code_host
    if code_host is None or project.installation is None:
        raise ApiError("connection.code_host_missing", 422)
    try:
        await code_host.apply_protection(project.installation, project.repository, project.branch)
        status = await code_host.read_protection(
            project.installation, project.repository, project.branch
        )
    except ProtectionRefusedError as refused:
        raise ApiError(refused.code, 422) from refused
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    now = datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        login = (
            await session.execute(
                text("SELECT login FROM people WHERE id = :id"), {"id": principal.person_id}
            )
        ).scalar_one()
        await store_protection(
            session, principal.organization_id, project_id, status, now, applied_by=login
        )
    return {"status": status.value, "branch": project.branch, "checkedAt": now.isoformat()}


__all__ = ["apply_protection"]
