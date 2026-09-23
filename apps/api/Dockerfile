# Pono API and worker — one image, two roles (PONO_ROLE unset: service; PONO_ROLE=worker).
# Built from the repository root because the uv workspace lives there.

FROM python:3.14-slim AS build
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/
RUN uv sync --frozen --no-dev --package pono-api --no-install-workspace

COPY apps/api apps/api
RUN uv sync --frozen --no-dev --package pono-api

FROM python:3.14-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN groupadd --system pono && useradd --system --gid pono --home-dir /app pono
COPY --from=build --chown=pono:pono /app/.venv /app/.venv
COPY --from=build --chown=pono:pono /app/apps/api /app/apps/api
WORKDIR /app/apps/api
USER pono
EXPOSE 8000

# No curl in the slim image: the probe is Python, and knows both roles.
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 CMD ["pono-healthcheck"]

# The service runs the migrations with the owner role before the port opens; the worker only
# reads and records, under the application role.
CMD ["sh", "-c", "if [ \"$PONO_ROLE\" = worker ]; then exec pono-worker; else alembic upgrade head && exec pono-api; fi"]
