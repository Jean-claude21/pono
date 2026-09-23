"""Guarded release: attempts, approval, protection, rollback, evidence journal (002)."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Response

from pono_api.api.dependencies import PrincipalDep, ProvidersDep, SessionsDep
from pono_api.api.schemas import ApprovalRequest, JournalEntry, Protection, Release, Rollback
from pono_api.application import journal
from pono_api.application.protection import apply_protection
from pono_api.application.refresh_project import Providers
from pono_api.application.releases import (
    approve_release,
    evaluate_project,
    list_releases,
    request_evaluation,
)
from pono_api.application.rollback import request_rollback
from pono_api.application.workshop import project_exists
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.api.releases")

router = APIRouter(tags=["releases"])


async def _release(
    sessions: SessionsDep, principal: Principal, project_id: UUID, release_id: UUID
) -> Release:
    for release in await list_releases(sessions, principal, project_id):
        if release["id"] == str(release_id):
            return Release.model_validate(release)
    raise ApiError("release.not_found", 404)


@router.get("/projects/{project_id}/releases")
async def read_releases(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep
) -> list[Release]:
    return [
        Release.model_validate(release)
        for release in await list_releases(sessions, principal, project_id)
    ]


async def _evaluate_in_background(
    sessions: SessionsDep, principal: Principal, project_id: UUID, providers: Providers
) -> None:
    try:
        await evaluate_project(sessions, principal, providers, project_id)
    except Exception:  # a background evaluation must never take the service down
        logger.exception("requested evaluation of project %s failed", project_id)


@router.post("/projects/{project_id}/releases/{release_id}/evaluation", status_code=202)
async def request_release_evaluation(
    project_id: UUID,
    release_id: UUID,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
    background: BackgroundTasks,
) -> Response:
    await request_evaluation(sessions, principal, project_id, release_id)
    background.add_task(_evaluate_in_background, sessions, principal, project_id, providers)
    return Response(status_code=202)


@router.post("/projects/{project_id}/releases/{release_id}/approval")
async def approve(
    project_id: UUID,
    release_id: UUID,
    request: ApprovalRequest,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
) -> Release:
    """Only a person's session reaches this route: no key, no agent token exists (FR-011)."""

    await approve_release(sessions, principal, providers, project_id, release_id, request.head_sha)
    return await _release(sessions, principal, project_id, release_id)


@router.post("/projects/{project_id}/protection")
async def protect(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Protection:
    return Protection.model_validate(
        await apply_protection(sessions, principal, providers, project_id)
    )


@router.post("/projects/{project_id}/rollback", status_code=202)
async def rollback(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Rollback:
    return Rollback.model_validate(
        await request_rollback(sessions, principal, providers, project_id)
    )


@router.get("/projects/{project_id}/journal")
async def read_journal(
    project_id: UUID,
    sessions: SessionsDep,
    principal: PrincipalDep,
    before: Annotated[UUID | None, Query()] = None,
) -> list[JournalEntry]:
    async with unit_of_work(sessions, principal) as session:
        if not await project_exists(session, project_id):
            raise not_found("project")
        entries = await journal.read(session, project_id, before)
    return [JournalEntry.model_validate(entry) for entry in entries]


__all__ = ["router"]
