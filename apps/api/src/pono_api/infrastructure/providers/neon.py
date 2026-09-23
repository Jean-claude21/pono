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
        payload = as_object(
            await self._client.get(f"/projects?limit=100&search={quote(name)}", "list_projects")
        )
        matches = [
            text(project, "id")
            for project in map(as_object, as_list(payload.get("projects")))
            if (text(project, "name") or "").lower() == name.lower()
        ]
        found = [match for match in matches if match]
        return found[0] if len(found) == 1 else None

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
