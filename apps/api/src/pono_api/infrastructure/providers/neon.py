"""Neon adapter for the database port: the project and branches a manifest references."""

from urllib.parse import quote

import httpx

from pono_api.application.ports import DatabaseSnapshot, KeyUse, ProviderUnavailableError
from pono_api.domain.projects import ResourceStatus
from pono_api.infrastructure.providers.http import KeyedClient, as_list, as_object, text

API_URL = "https://console.neon.tech/api/v2"


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
