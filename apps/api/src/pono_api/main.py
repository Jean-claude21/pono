"""FastAPI application: routers under /api/v1, stable errors, health."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from sqlalchemy import text

from pono_api.api import auth, connections, me, projects
from pono_api.api.errors import install_error_handlers
from pono_api.application.identity import CodeHostIdentity
from pono_api.application.refresh_project import Providers
from pono_api.config import Settings, get_settings
from pono_api.infrastructure.database.session import create_engine, create_session_factory
from pono_api.infrastructure.logging import configure_logging
from pono_api.infrastructure.providers.defaults import default_providers
from pono_api.infrastructure.providers.github_identity import GitHubIdentity

API_PREFIX = "/api/v1"


def _default_identity(settings: Settings) -> CodeHostIdentity | None:
    if settings.github_client_id and settings.github_client_secret:
        return GitHubIdentity(settings.github_client_id, settings.github_client_secret)
    return None


def create_app(
    settings: Settings | None = None,
    identity: CodeHostIdentity | None = None,
    providers: Providers | None = None,
) -> FastAPI:
    settings = settings or get_settings()

    # Resources are built eagerly so the app works with or without a lifespan-aware server;
    # the lifespan only releases them.
    engine = create_engine(settings.database_app_url) if settings.database_app_url else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            await engine.dispose()

    app = FastAPI(
        title="Pono API", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.state.settings = settings
    app.state.identity = identity or _default_identity(settings)
    app.state.providers = providers or default_providers(settings)
    app.state.engine = engine
    app.state.sessions = create_session_factory(engine) if engine else None
    install_error_handlers(app)

    health = APIRouter(tags=["health"])

    @health.get("/health")
    async def read_health(request: Request) -> dict[str, str]:
        sessions = getattr(request.app.state, "sessions", None)
        database = "unconfigured"
        if sessions is not None:
            try:
                async with sessions() as session:
                    await session.execute(text("SELECT 1"))
                database = "ok"
            except Exception:  # health must answer even when the database does not
                database = "error"
        return {
            "status": "ok",
            "database": database,
            "email": "configured" if settings.smtp_configured else "not_configured",
            "chat": "configured" if settings.chat_configured else "not_configured",
        }

    for router in (health, auth.router, me.router, connections.router, projects.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


def run() -> None:
    settings = get_settings()
    configure_logging()
    uvicorn.run(create_app(settings), host="0.0.0.0", port=8000, log_config=None)  # noqa: S104


app = create_app()

__all__ = ["app", "create_app", "run"]
