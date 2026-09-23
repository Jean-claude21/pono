"""GitHub App adapter for the code host port, ported from KYA-Platform's pull-request adapter.

It authenticates as an installation with short-lived tokens (research R-03). Every write goes
through `_write`, which refuses any branch outside `pono/*` before a request leaves (FR-029).
There is no merge operation: merging stays a human gesture on GitHub.
"""

import base64
import time
from datetime import datetime
from typing import cast
from urllib.parse import quote

import httpx
import jwt
from pydantic import SecretStr

from pono_api.application.ports import (
    ForbiddenWriteError,
    ProposalState,
    ProviderUnavailableError,
    RepositoryInfo,
)
from pono_api.domain.projects import is_proposal_branch

JsonObject = dict[str, object]
TOKEN_LIFETIME_SECONDS = 50 * 60


def _object(value: object) -> JsonObject:
    if not isinstance(value, dict):
        raise ProviderUnavailableError("code host returned an unexpected payload")
    return cast(JsonObject, value)


def _string(payload: JsonObject, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ProviderUnavailableError(f"code host response is missing '{key}'")
    return value


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _pull_request_path(proposal_url: str) -> str:
    # https://github.com/{owner}/{repo}/pull/{number}
    parts = proposal_url.rstrip("/").split("/")
    if len(parts) < 4 or parts[-2] != "pull" or not parts[-1].isdigit():
        raise ProviderUnavailableError("malformed proposal url")
    return f"/repos/{parts[-4]}/{parts[-3]}/pulls/{parts[-1]}"


class GitHubCodeHost:
    def __init__(
        self,
        *,
        app_id: str,
        private_key: SecretStr,
        api_url: str = "https://api.github.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not app_id or not private_key.get_secret_value():
            raise ValueError("GitHub App credentials are required")
        self._app_id = app_id
        self._private_key = private_key
        self._api_url = api_url.rstrip("/")
        self._transport = transport
        self._tokens: dict[str, tuple[str, float]] = {}

    # --- installations ------------------------------------------------------------------------

    async def find_installation(self, account_id: str) -> str | None:
        page = 1
        while True:
            response = await self._app_request(
                "GET", f"/app/installations?per_page=100&page={page}"
            )
            installations = response.json()
            if not isinstance(installations, list):
                raise ProviderUnavailableError("code host returned an unexpected payload")
            for item in installations:
                installation = _object(item)
                account = _object(installation.get("account"))
                if str(account.get("id")) == account_id:
                    return str(installation.get("id"))
            if len(installations) < 100:
                return None
            page += 1

    async def installation_active(self, installation_id: str) -> bool:
        response = await self._app_request(
            "GET", f"/app/installations/{quote(installation_id)}", allow={404}
        )
        return response.status_code == 200

    async def revoke_installation(self, installation_id: str) -> None:
        await self._app_request(
            "DELETE", f"/app/installations/{quote(installation_id)}", allow={404}
        )
        self._tokens.pop(installation_id, None)

    # --- reads --------------------------------------------------------------------------------

    async def list_repositories(self, installation_id: str) -> list[RepositoryInfo]:
        repositories: list[RepositoryInfo] = []
        page = 1
        while True:
            payload = _object(
                (
                    await self._request(
                        installation_id,
                        "GET",
                        f"/installation/repositories?per_page=100&page={page}",
                    )
                ).json()
            )
            items = payload.get("repositories")
            if not isinstance(items, list):
                raise ProviderUnavailableError("code host returned an unexpected payload")
            for item in items:
                repository = _object(item)
                repositories.append(
                    RepositoryInfo(
                        full_name=_string(repository, "full_name"),
                        default_branch=_string(repository, "default_branch"),
                    )
                )
            if len(items) < 100:
                return repositories
            page += 1

    async def read_file(
        self, installation_id: str, repository: str, path: str, ref: str | None = None
    ) -> str | None:
        query = f"?ref={quote(ref)}" if ref else ""
        response = await self._request(
            installation_id,
            "GET",
            f"/repos/{repository}/contents/{quote(path)}{query}",
            accept="application/vnd.github.raw+json",
            allow={404},
        )
        if response.status_code == 404:
            return None
        return response.text

    async def last_push_at(self, installation_id: str, repository: str) -> datetime | None:
        payload = _object(
            (await self._request(installation_id, "GET", f"/repos/{repository}")).json()
        )
        return _timestamp(payload.get("pushed_at"))

    async def commit_author(
        self, installation_id: str, repository: str, commit_sha: str
    ) -> str | None:
        response = await self._request(
            installation_id,
            "GET",
            f"/repos/{repository}/commits/{quote(commit_sha)}",
            allow={404, 422},
        )
        if response.status_code != 200:
            return None
        payload = _object(response.json())
        author = payload.get("author")
        if isinstance(author, dict) and isinstance(author.get("login"), str):
            return cast(str, author["login"])
        commit = payload.get("commit")
        if isinstance(commit, dict) and isinstance(commit.get("author"), dict):
            name = cast(JsonObject, commit["author"]).get("name")
            return name if isinstance(name, str) else None
        return None

    async def proposal_state(self, installation_id: str, proposal_url: str) -> ProposalState:
        payload = _object(
            (await self._request(installation_id, "GET", _pull_request_path(proposal_url))).json()
        )
        if payload.get("merged") is True:
            return "merged"
        return "closed" if payload.get("state") == "closed" else "open"

    # --- the only write path ------------------------------------------------------------------

    async def propose_file(
        self,
        installation_id: str,
        repository: str,
        *,
        base: str,
        branch: str,
        path: str,
        content: str,
        title: str,
        body: str,
    ) -> str:
        self._guard(branch)
        base_ref = _object(
            (
                await self._request(
                    installation_id, "GET", f"/repos/{repository}/git/ref/heads/{quote(base)}"
                )
            ).json()
        )
        base_sha = _string(_object(base_ref.get("object")), "sha")
        created = await self._write(
            installation_id,
            branch,
            "POST",
            f"/repos/{repository}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": base_sha},
            allow={422},
        )
        existing_sha: str | None = None
        if created.status_code == 422:
            # The branch survives from an earlier proposal: update the file in place on it.
            existing = await self._request(
                installation_id,
                "GET",
                f"/repos/{repository}/contents/{quote(path)}?ref={quote(branch)}",
                allow={404},
            )
            if existing.status_code == 200:
                existing_sha = _string(_object(existing.json()), "sha")
        file_payload: JsonObject = {
            "message": title,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if existing_sha:
            file_payload["sha"] = existing_sha
        await self._write(
            installation_id,
            branch,
            "PUT",
            f"/repos/{repository}/contents/{quote(path)}",
            file_payload,
        )
        opened = await self._write(
            installation_id,
            branch,
            "POST",
            f"/repos/{repository}/pulls",
            {"title": title, "head": branch, "base": base, "body": body},
            allow={422},
        )
        if opened.status_code != 422:
            return _string(_object(opened.json()), "html_url")
        owner = repository.split("/", 1)[0]
        listed = (
            await self._request(
                installation_id,
                "GET",
                f"/repos/{repository}/pulls?state=open&head={quote(f'{owner}:{branch}')}",
            )
        ).json()
        if not isinstance(listed, list) or not listed:
            raise ProviderUnavailableError("code host refused the pull request")
        return _string(_object(listed[0]), "html_url")

    @staticmethod
    def _guard(branch: str) -> None:
        if not is_proposal_branch(branch):
            raise ForbiddenWriteError(f"writes are only allowed on proposal branches: {branch}")

    async def _write(
        self,
        installation_id: str,
        branch: str,
        method: str,
        path: str,
        payload: JsonObject,
        *,
        allow: set[int] | None = None,
    ) -> httpx.Response:
        self._guard(branch)
        return await self._request(installation_id, method, path, json=payload, allow=allow)

    # --- transport ----------------------------------------------------------------------------

    def _app_jwt(self) -> str:
        now = int(time.time())
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": self._app_id},
            self._private_key.get_secret_value(),
            algorithm="RS256",
        )

    async def _app_request(
        self, method: str, path: str, *, allow: set[int] | None = None
    ) -> httpx.Response:
        return await self._send(method, path, f"Bearer {self._app_jwt()}", allow=allow)

    async def _installation_token(self, installation_id: str) -> str:
        cached = self._tokens.get(installation_id)
        if cached is not None and time.time() < cached[1]:
            return cached[0]
        response = await self._app_request(
            "POST", f"/app/installations/{quote(installation_id)}/access_tokens"
        )
        token = _string(_object(response.json()), "token")
        self._tokens[installation_id] = (token, time.time() + TOKEN_LIFETIME_SECONDS)
        return token

    async def _request(
        self,
        installation_id: str,
        method: str,
        path: str,
        *,
        json: JsonObject | None = None,
        accept: str = "application/vnd.github+json",
        allow: set[int] | None = None,
    ) -> httpx.Response:
        token = await self._installation_token(installation_id)
        return await self._send(
            method, path, f"Bearer {token}", json=json, accept=accept, allow=allow
        )

    async def _send(
        self,
        method: str,
        path: str,
        authorization: str,
        *,
        json: JsonObject | None = None,
        accept: str = "application/vnd.github+json",
        allow: set[int] | None = None,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=15) as client:
                response = await client.request(
                    method,
                    f"{self._api_url}{path}",
                    headers={
                        "Authorization": authorization,
                        "Accept": accept,
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json=json,
                )
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(f"code host {method} {path} failed") from error
        if response.status_code >= 400 and response.status_code not in (allow or set()):
            raise ProviderUnavailableError(
                f"code host {method} {path} answered {response.status_code}"
            )
        return response


__all__ = ["GitHubCodeHost"]
