"""Neon adapter for the database port: the project and branches a manifest references."""

from urllib.parse import quote

import httpx

from pono_api.application.ports import DatabaseSnapshot, KeyUse, ProviderUnavailableError
from pono_api.domain.projects import ResourceStatus
from pono_api.domain.quotas import LimitSource, Metric, QuotaReading
from pono_api.infrastructure.providers.http import (
    KeyedClient,
    as_list,
    as_object,
    text,
    timestamp,
)

API_URL = "https://console.neon.tech/api/v2"

# The free plan, as published on neon.com/pricing (read 2026-09-23, research R-08). The API states
# the storage limit; it does not state these two, so they are shown as estimates.
FREE_COMPUTE_SECONDS = 100 * 3600  # 100 CU-hours per project and month
FREE_TRANSFER_BYTES = 5 * 1000**3  # 5 GB of public egress per project and month


class NeonDatabase:
    def __init__(
        self,
        token: str,
        on_use: KeyUse,
        *,
        api_url: str = API_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = KeyedClient(api_url, token, on_use, provider="neon", transport=transport)

    async def verify(self) -> str:
        user = as_object(await self._client.get("/users/me", "verify_user"))
        reference = text(user, "id") or text(user, "login")
        if reference is None:
            raise ProviderUnavailableError("neon returned no account")
        return reference

    async def find_project(self, name: str) -> str | None:
        """The one project with exactly this name, across every organization the key reaches."""

        found: set[str] = set()
        for organization in await self._organizations():
            payload = as_object(
                await self._client.get(
                    f"/projects?limit=100&org_id={quote(organization)}&search={quote(name)}",
                    "list_projects",
                )
            )
            found.update(
                reference
                for project in map(as_object, as_list(payload.get("projects")))
                if (text(project, "name") or "").lower() == name.lower()
                and (reference := text(project, "id")) is not None
            )
        return found.pop() if len(found) == 1 else None

    async def read_quotas(self, ref: str) -> list[QuotaReading]:
        project = as_object(
            as_object(await self._client.get(f"/projects/{quote(ref)}", "read_consumption")).get(
                "project"
            )
        )
        start = timestamp(project.get("consumption_period_start"))
        if start is None:
            return []
        end = timestamp(project.get("consumption_period_end"))
        free = await self._on_free_plan(text(project, "org_id"))

        def reading(
            metric: Metric, used: object, limit: object, source: LimitSource
        ) -> QuotaReading | None:
            if not isinstance(used, int | float):
                return None
            return QuotaReading(
                metric=metric,
                used=float(used),
                limit=float(limit) if isinstance(limit, int | float) and limit else None,
                limit_source=source,
                period_start=start.date(),
                period_end=end.date() if end else None,
            )

        readings = [
            reading(
                Metric.DB_COMPUTE_SECONDS,
                project.get("compute_time_seconds"),
                FREE_COMPUTE_SECONDS if free else None,
                LimitSource.FREE_TIER_ESTIMATE,
            ),
            reading(
                Metric.DB_STORAGE_BYTES,
                project.get("synthetic_storage_size"),
                project.get("branch_logical_size_limit_bytes"),
                LimitSource.ACCOUNT_PLAN,
            ),
            reading(
                Metric.DB_TRANSFER_BYTES,
                project.get("data_transfer_bytes"),
                FREE_TRANSFER_BYTES if free else None,
                LimitSource.FREE_TIER_ESTIMATE,
            ),
        ]
        return [item for item in readings if item is not None]

    async def _on_free_plan(self, organization: str | None) -> bool:
        if organization is None:
            user = as_object(await self._client.get("/users/me", "read_plan"))
            return (text(user, "plan") or "").startswith("free")
        detail = as_object(
            await self._client.get(f"/organizations/{quote(organization)}", "read_plan")
        )
        return (text(detail, "plan") or "").startswith("free")

    async def _organizations(self) -> list[str]:
        # Listing projects needs an organization: a key reaches its user's organizations.
        payload = as_object(await self._client.get("/users/me/organizations", "list_organizations"))
        return [
            reference
            for organization in map(as_object, as_list(payload.get("organizations")))
            if (reference := text(organization, "id")) is not None
        ]

    async def read_project(self, ref: str) -> DatabaseSnapshot:
        project = await self._client.get(
            f"/projects/{quote(ref)}", "read_project", allow_missing=True
        )
        if project is None:
            return DatabaseSnapshot(status=ResourceStatus.MISSING)
        branches = as_object(
            await self._client.get(f"/projects/{quote(ref)}/branches", "read_branches")
        )
        names = tuple(
            name
            for branch in map(as_object, as_list(branches.get("branches")))
            if (name := text(branch, "name")) is not None
        )
        return DatabaseSnapshot(status=ResourceStatus.FOUND, branches=names)


__all__ = ["NeonDatabase"]
