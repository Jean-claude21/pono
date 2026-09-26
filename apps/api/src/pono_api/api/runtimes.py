"""A project's development runtime, from the console (004 contracts/openapi.yaml).

Agents call the same functions through their tools (principle VIII): the console has every gesture,
including writing a file without an agent (clarification of US2).
"""

import base64
import binascii
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from pono_api.api.dependencies import PrincipalDep, ProvidersDep, SessionsDep
from pono_api.api.schemas import (
    FileWrite,
    Runtime,
    RuntimeErrors,
    TicketRequest,
    TicketUrl,
    WriteResult,
)
from pono_api.application.runtime_writes import save_now, write_file
from pono_api.application.runtimes import (
    read_errors,
    read_runtime,
    request_runtime,
    runtime_ticket,
    stop_runtime,
)
from pono_api.errors import ApiError

router = APIRouter(prefix="/projects/{project_id}/runtime", tags=["runtime"])


@router.get("")
async def get_runtime(project_id: UUID, sessions: SessionsDep, principal: PrincipalDep) -> Runtime:
    return Runtime.model_validate(await read_runtime(sessions, principal, project_id))


@router.post("", status_code=202)
async def start_runtime(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Runtime:
    return Runtime.model_validate(await request_runtime(sessions, principal, providers, project_id))


@router.delete("")
async def stop(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Runtime:
    return Runtime.model_validate(await stop_runtime(sessions, principal, providers, project_id))


def _content(body: FileWrite) -> bytes:
    if body.content_base64 is not None:
        try:
            return base64.b64decode(body.content_base64, validate=True)
        except binascii.Error as error:
            raise ApiError("request.invalid", 422, "contentBase64") from error
    if body.content is None:
        raise ApiError("request.invalid", 422, "content")
    return body.content.encode()


@router.put("/files")
async def put_file(
    project_id: UUID,
    body: FileWrite,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
) -> WriteResult:
    written = await write_file(
        sessions, principal, providers, project_id, body.path, _content(body)
    )
    return WriteResult.model_validate(written)


@router.delete("/files")
async def delete_file(
    project_id: UUID,
    path: Annotated[str, Query(min_length=1, max_length=512)],
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
) -> WriteResult:
    written = await write_file(sessions, principal, providers, project_id, path, None)
    return WriteResult.model_validate(written)


@router.post("/save")
async def save(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Runtime:
    await save_now(sessions, principal, providers, project_id)
    return Runtime.model_validate(await read_runtime(sessions, principal, project_id))


@router.get("/errors")
async def errors(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> RuntimeErrors:
    return RuntimeErrors.model_validate(
        await read_errors(sessions, principal, providers, project_id)
    )


@router.post("/ticket")
async def ticket(
    project_id: UUID,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
    body: TicketRequest | None = None,
) -> TicketUrl:
    """A one-time pass for a signed-in member's browser (research R-04)."""

    url = await runtime_ticket(
        sessions, principal, providers, project_id, body.return_ if body else None
    )
    return TicketUrl(url=url)


__all__ = ["router"]
