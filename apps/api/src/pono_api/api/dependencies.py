"""Request dependencies: settings, database sessions, identity provider, current principal."""

from typing import Annotated, cast

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.identity import CodeHostIdentity
from pono_api.application.refresh_project import Providers
from pono_api.application.sessions import SESSION_COOKIE, resolve_session
from pono_api.config import Settings
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    sessions = getattr(request.app.state, "sessions", None)
    if sessions is None:
        raise ApiError("service.database_unconfigured", 503)
    return cast(async_sessionmaker[AsyncSession], sessions)


def get_identity(request: Request) -> CodeHostIdentity:
    identity = getattr(request.app.state, "identity", None)
    if identity is None:
        raise ApiError("service.identity_unconfigured", 503)
    return cast(CodeHostIdentity, identity)


def get_providers(request: Request) -> Providers:
    providers = getattr(request.app.state, "providers", None)
    if providers is None:
        raise ApiError("service.providers_unconfigured", 503)
    return cast(Providers, providers)


async def current_principal(
    sessions: Annotated[async_sessionmaker[AsyncSession], Depends(get_sessions)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Principal:
    principal = await resolve_session(sessions, token)
    if principal is None or not principal.organization_ids:
        raise ApiError("auth.session_required", 401)
    return principal


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionsDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessions)]
IdentityDep = Annotated[CodeHostIdentity, Depends(get_identity)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]
PrincipalDep = Annotated[Principal, Depends(current_principal)]

__all__ = [
    "IdentityDep",
    "PrincipalDep",
    "ProvidersDep",
    "SessionsDep",
    "SettingsDep",
    "current_principal",
    "get_identity",
    "get_providers",
    "get_sessions",
    "get_settings",
]
