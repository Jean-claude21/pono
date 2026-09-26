"""Agents' access, seen and decided in the console (003 US1, US3, US4)."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from pono_api.api.dependencies import PrincipalDep, ProvidersDep, SessionsDep
from pono_api.api.schemas import (
    AgentGrant,
    ConsentDecision,
    ConsentRedirect,
    ConsentRequest,
    ProjectDetail,
)
from pono_api.application.agent_access import (
    consent_view,
    decide_consent,
    list_agents,
    revoke_agent,
)
from pono_api.application.rollback_requests import decide_rollback_request
from pono_api.application.workshop import load_project
from pono_api.errors import ApiError
from pono_api.infrastructure.oauth.broker import AgentBroker

router = APIRouter(tags=["agents"])


def _broker(request: Request) -> AgentBroker:
    broker = getattr(request.app.state, "agent_broker", None)
    if broker is None:
        raise ApiError("service.agents_unconfigured", 503)
    return cast(AgentBroker, broker)


@router.get("/oauth/consent")
async def read_consent(
    request: Request,
    sessions: SessionsDep,
    principal: PrincipalDep,
    handle: Annotated[str, Query(alias="request", min_length=16)],
) -> ConsentRequest:
    return ConsentRequest.model_validate(
        await consent_view(sessions, principal, _broker(request), handle)
    )


@router.post("/oauth/consent/{decision}")
async def decide(
    decision: Literal["approve", "deny"],
    body: ConsentDecision,
    request: Request,
    principal: PrincipalDep,
) -> ConsentRedirect:
    """Only a signed-in person reaches this: the consent is a human gesture (003 FR-002)."""

    redirect = await decide_consent(
        principal, _broker(request), body.request, body.access, decision == "approve"
    )
    return ConsentRedirect(redirect_url=redirect)


@router.get("/agents")
async def read_agents(sessions: SessionsDep, principal: PrincipalDep) -> list[AgentGrant]:
    return [AgentGrant.model_validate(item) for item in await list_agents(sessions, principal)]


@router.delete("/agents/{grant_id}", status_code=204)
async def cut_agent(grant_id: UUID, sessions: SessionsDep, principal: PrincipalDep) -> Response:
    await revoke_agent(sessions, principal, grant_id)
    return Response(status_code=204)


@router.post("/projects/{project_id}/rollback-requests/{request_id}/{decision}")
async def decide_rollback(
    project_id: UUID,
    request_id: UUID,
    decision: Literal["confirm", "dismiss"],
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
) -> ProjectDetail:
    """A person confirms (the rollback runs) or dismisses an agent's rollback request."""

    await decide_rollback_request(
        sessions, principal, providers, project_id, request_id, confirm=decision == "confirm"
    )
    return ProjectDetail.model_validate(await load_project(sessions, principal, project_id))


__all__ = ["router"]
