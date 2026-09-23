"""Provider connections of the current organization (FR-010 to FR-013)."""

from uuid import UUID

from fastapi import APIRouter, Response

from pono_api.api.dependencies import PrincipalDep, ProvidersDep, SessionsDep
from pono_api.api.schemas import Connection, ConnectionRequest
from pono_api.application.connections import (
    link_code_host,
    list_connections,
    register_connection,
    revoke_connection,
)
from pono_api.domain.projects import ConnectionKind
from pono_api.errors import ApiError

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("")
async def read_connections(sessions: SessionsDep, principal: PrincipalDep) -> list[Connection]:
    connections = await list_connections(sessions, principal)
    return [Connection.model_validate(view.to_payload()) for view in connections]


@router.post("/code-host", status_code=201)
async def connect_code_host(
    sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Connection:
    """Link the installation of the Pono app on the person's account: no key is asked (FR-010)."""

    if providers.code_host is None:
        raise ApiError("service.code_host_unconfigured", 503)
    view = await link_code_host(sessions, principal, providers.code_host)
    return Connection.model_validate(view.to_payload())


@router.post("", status_code=201)
async def create_connection(
    request: ConnectionRequest,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
) -> Connection:
    view = await register_connection(
        sessions,
        principal,
        providers.factory,
        kind=ConnectionKind(request.kind),
        provider=request.provider,
        authorization=request.authorization.get_secret_value(),
        endpoint=request.endpoint,
    )
    return Connection.model_validate(view.to_payload())


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    connection_id: UUID, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> Response:
    await revoke_connection(sessions, principal, providers.code_host, connection_id)
    return Response(status_code=204)


__all__ = ["router"]
