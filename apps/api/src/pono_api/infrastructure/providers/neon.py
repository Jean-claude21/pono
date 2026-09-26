"""Neon adapter for the database port: the project and branches a manifest references."""

from urllib.parse import quote

import httpx

from pono_api.application.ports import (
    DatabaseSnapshot,
    DevelopmentDatabase,
    DevelopmentDatabaseError,
    KeyUse,
    ProviderUnavailableError,
)
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

# The account reference of an organization key that reaches no project yet.
ORGANIZATION_KEY = "organization"


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
        """The account a key reaches: a person for a personal key, an organization otherwise.

        Neon answers 404 on `/users/me` for an organization key: that is not an outage, the key
        simply belongs to no person. Its organization shows on the projects it can list.
        """

        user = await self._client.get("/users/me", "verify_user", allow_missing=True)
        if user is not None:
            reference = text(as_object(user), "id") or text(as_object(user), "login")
            if reference is None:
                raise ProviderUnavailableError("neon returned no account")
            return reference
        listing = as_object(await self._client.get("/projects?limit=1", "verify_projects"))
        projects = [as_object(project) for project in as_list(listing.get("projects"))]
        organization = text(projects[0], "org_id") if projects else None
        return organization or ORGANIZATION_KEY

    async def find_project(self, name: str) -> str | None:
        """The one project with exactly this name, across every organization the key reaches."""

        found: set[str] = set()
        for organization in await self._organizations():
            scope = f"&org_id={quote(organization)}" if organization else ""
            payload = as_object(
                await self._client.get(
                    f"/projects?limit=100{scope}&search={quote(name)}", "list_projects"
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
            user = await self._client.get("/users/me", "read_plan", allow_missing=True)
            return (text(as_object(user), "plan") or "").startswith("free")
        detail = as_object(
            await self._client.get(f"/organizations/{quote(organization)}", "read_plan")
        )
        return (text(detail, "plan") or "").startswith("free")

    async def _organizations(self) -> list[str | None]:
        """Where to list projects. A personal key names its user's organizations; an organization
        key has no user (404) and lists its own organization without naming it (None)."""

        payload = await self._client.get(
            "/users/me/organizations", "list_organizations", allow_missing=True
        )
        if payload is None:
            return [None]
        return [
            reference
            for organization in map(as_object, as_list(as_object(payload).get("organizations")))
            if (reference := text(organization, "id")) is not None
        ]

    async def development_target(
        self, ref: str, development_branch: str, production_branch: str | None
    ) -> DevelopmentDatabase:
        """The development branch's address, never the production's (004 research R-03)."""

        if production_branch and development_branch == production_branch:
            raise DevelopmentDatabaseError("runtime.production_database")
        project = quote(ref)
        branch = await self._client.get(
            f"/projects/{project}/branches/{quote(development_branch)}",
            "read_branch",
            allow_missing=True,
        )
        if branch is None:
            raise DevelopmentDatabaseError("runtime.database_missing")
        detail = as_object(as_object(branch).get("branch"))
        if detail.get("default") is True or detail.get("primary") is True:
            raise DevelopmentDatabaseError("runtime.production_database")
        endpoints = as_object(
            await self._client.get(f"/projects/{project}/endpoints", "read_endpoints")
        )
        hosts = {
            text(endpoint, "branch_id"): text(endpoint, "host")
            for endpoint in map(as_object, as_list(endpoints.get("endpoints")))
            if text(endpoint, "type") == "read_write"
        }
        host = hosts.get(development_branch)
        production_host = hosts.get(production_branch) if production_branch else None
        if host is None:
            raise DevelopmentDatabaseError("runtime.database_missing")
        if production_host is not None and host == production_host:
            raise DevelopmentDatabaseError("runtime.production_database")
        databases = [
            as_object(item)
            for item in as_list(
                as_object(
                    await self._client.get(
                        f"/projects/{project}/branches/{quote(development_branch)}/databases",
                        "read_databases",
                    )
                ).get("databases")
            )
        ]
        if not databases:
            raise DevelopmentDatabaseError("runtime.database_missing")
        database = databases[0]
        name, role = text(database, "name"), text(database, "owner_name")
        if name is None or role is None:
            raise DevelopmentDatabaseError("runtime.database_missing")
        address = as_object(
            await self._client.get(
                f"/projects/{project}/connection_uri?branch_id={quote(development_branch)}"
                f"&database_name={quote(name)}&role_name={quote(role)}",
                "read_connection_uri",
            )
        )
        url = text(address, "uri")
        if url is None:
            raise ProviderUnavailableError("neon returned no connection address")
        return DevelopmentDatabase(url=url, host=host, production_host=production_host)

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
