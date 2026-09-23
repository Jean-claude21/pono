"""GitHub App adapter for the code host port, ported from KYA-Platform's pull-request adapter.

It authenticates as an installation with short-lived tokens (research R-03). Every write on a
branch goes through `_write`, which refuses any branch outside `pono/*` before a request leaves
(FR-029). Phase 2 adds exactly two bounded writes, each with its own guard: the `pono/release` check
run, and the protection rule of a production branch (002 research R-01, R-07). There is no merge
operation: merging stays a human gesture on GitHub.
"""

import base64
import re
import time
from datetime import datetime
from typing import cast
from urllib.parse import quote

import httpx
import jwt
from pydantic import SecretStr

from pono_api.application.guards.secrets import is_binary
from pono_api.application.ports import (
    ChangedFile,
    ChangeRequest,
    CheckState,
    ForbiddenWriteError,
    ProposalState,
    ProtectionRefusedError,
    ProviderUnavailableError,
    RepositoryInfo,
)
from pono_api.domain.projects import is_proposal_branch
from pono_api.domain.releases import RELEASE_CHECK_NAME, ProtectionStatus

JsonObject = dict[str, object]
TOKEN_LIFETIME_SECONDS = 50 * 60
# A query, never a mutation: the only write path is `_write`.
BRANCH_HEADS_QUERY = (
    "query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { "
    'refs(refPrefix: "refs/heads/", first: 100) { nodes { name target { '
    "... on Commit { committedDate } } } } } }"
)


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


_PLAN_REFUSAL = "upgrade to github pro"
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _change(payload: JsonObject) -> ChangeRequest:
    user, head, base = (_object(payload.get(key) or {}) for key in ("user", "head", "base"))
    state: ProposalState = "open"
    if payload.get("merged") is True or payload.get("merged_at"):
        state = "merged"
    elif payload.get("state") == "closed":
        state = "closed"
    number = payload.get("number")
    if not isinstance(number, int):
        raise ProviderUnavailableError("code host response is missing 'number'")
    head_ref = head.get("ref")
    return ChangeRequest(
        number=number,
        url=_string(payload, "html_url"),
        title=str(payload.get("title") or ""),
        author=str(user.get("login") or "unknown"),
        author_is_agent=user.get("type") == "Bot",
        head_sha=_string(head, "sha"),
        head_branch=head_ref if isinstance(head_ref, str) else None,
        base_branch=_string(base, "ref"),
        state=state,
    )


def _enabled(protection: JsonObject, key: str) -> bool:
    return _object(protection.get(key) or {}).get("enabled") is True


def _names(restrictions: JsonObject, key: str, field: str) -> list[object]:
    items = restrictions.get(key)
    return [_object(item).get(field) for item in (items if isinstance(items, list) else [])]


def _pull_request_path(proposal_url: str) -> str:
    # https://github.com/{owner}/{repo}/pull/{number}
    parts = proposal_url.rstrip("/").split("/")
    if len(parts) < 4 or parts[-2] != "pull" or not parts[-1].isdigit():
        raise ProviderUnavailableError("malformed proposal url")
    return f"/repos/{parts[-4]}/{parts[-3]}/pulls/{parts[-1]}"


class GitHubCodeHost:
    provider = "github"

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

    async def last_commit_at(self, installation_id: str, repository: str) -> datetime | None:
        """One read-only GraphQL query over every branch head; `pono/*` branches do not count,
        so a proposal Pono opens never passes for the person's own activity."""

        owner, name = repository.split("/", 1)
        response = await self._request(
            installation_id,
            "POST",
            "/graphql",
            json={"query": BRANCH_HEADS_QUERY, "variables": {"owner": owner, "name": name}},
        )
        repository_node = _object(_object(_object(response.json()).get("data")).get("repository"))
        refs = _object(repository_node.get("refs")).get("nodes")
        moments = [
            _timestamp(_object(_object(ref).get("target")).get("committedDate"))
            for ref in (refs if isinstance(refs, list) else [])
            if not is_proposal_branch(str(_object(ref).get("name", "")))
        ]
        known = [moment for moment in moments if moment is not None]
        return max(known) if known else None

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

    # --- guarded release: reads ---------------------------------------------------------------

    async def list_changes(
        self, installation_id: str, repository: str, base_branch: str
    ) -> list[ChangeRequest]:
        payload = (
            await self._request(
                installation_id,
                "GET",
                f"/repos/{repository}/pulls?state=open&base={quote(base_branch)}&per_page=100",
            )
        ).json()
        if not isinstance(payload, list):
            raise ProviderUnavailableError("code host returned an unexpected payload")
        return [_change(_object(item)) for item in payload]

    async def read_change(
        self, installation_id: str, repository: str, number: int
    ) -> ChangeRequest:
        response = await self._request(
            installation_id, "GET", f"/repos/{repository}/pulls/{number}"
        )
        return _change(_object(response.json()))

    async def change_files(
        self, installation_id: str, repository: str, number: int
    ) -> list[ChangedFile]:
        files: list[ChangedFile] = []
        page = 1
        while True:
            batch = (
                await self._request(
                    installation_id,
                    "GET",
                    f"/repos/{repository}/pulls/{number}/files?per_page=100&page={page}",
                )
            ).json()
            if not isinstance(batch, list):
                raise ProviderUnavailableError("code host returned an unexpected payload")
            for item in batch:
                changed = _object(item)
                path = _string(changed, "filename")
                patch = changed.get("patch")
                files.append(
                    ChangedFile(
                        path=path,
                        status=str(changed.get("status") or "modified"),
                        patch=patch if isinstance(patch, str) else None,
                        binary=not isinstance(patch, str) and is_binary(path),
                    )
                )
            if len(batch) < 100:
                return files
            # The code host lists at most 3000 files: past that, the change cannot be read whole.
            if page == 30:
                raise ProviderUnavailableError("change too large to be read whole")
            page += 1

    async def read_protection(
        self, installation_id: str, repository: str, branch: str
    ) -> ProtectionStatus:
        response = await self._request(
            installation_id,
            "GET",
            f"/repos/{repository}/branches/{quote(branch)}/protection",
            allow={403, 404},
        )
        if response.status_code == 404:
            return ProtectionStatus.UNPROTECTED
        if response.status_code == 403:
            message = str(_object(response.json()).get("message", "")).lower()
            if _PLAN_REFUSAL in message:
                return ProtectionStatus.UNAVAILABLE_ON_PLAN
            return ProtectionStatus.UNKNOWN  # the app cannot read it yet: never claim either way
        if self._holds(_object(response.json())):
            return ProtectionStatus.PROTECTED
        return ProtectionStatus.UNPROTECTED

    def _holds(self, protection: JsonObject) -> bool:
        checks = _object(protection.get("required_status_checks") or {}).get("checks")
        ours = any(
            _object(check).get("context") == RELEASE_CHECK_NAME
            and str(_object(check).get("app_id")) == self._app_id
            for check in (checks if isinstance(checks, list) else [])
        )
        return (
            ours
            and protection.get("required_pull_request_reviews") is not None
            and _enabled(protection, "enforce_admins")
            and not _enabled(protection, "allow_force_pushes")
            and not _enabled(protection, "allow_deletions")
        )

    # --- guarded release: the two bounded writes ----------------------------------------------

    async def set_release_check(
        self,
        installation_id: str,
        repository: str,
        head_sha: str,
        state: CheckState,
        *,
        summary: str,
        details_url: str | None,
    ) -> None:
        payload: JsonObject = {
            "name": RELEASE_CHECK_NAME,
            "head_sha": head_sha,
            "output": {"title": summary, "summary": summary},
        }
        if details_url:
            payload["details_url"] = details_url
        if state == "pending":
            payload["status"] = "in_progress"
        else:
            payload["status"] = "completed"
            payload["conclusion"] = state
        await self._check_write(installation_id, repository, payload)

    async def apply_protection(self, installation_id: str, repository: str, branch: str) -> None:
        """Adds Pono's rule to whatever protection the branch already has, never removes one."""

        current = await self._request(
            installation_id,
            "GET",
            f"/repos/{repository}/branches/{quote(branch)}/protection",
            allow={403, 404},
        )
        if current.status_code == 403:
            self._refusal(current)
        existing = _object(current.json()) if current.status_code == 200 else {}
        await self._protection_write(installation_id, repository, branch, self._rule(existing))

    def _rule(self, existing: JsonObject) -> JsonObject:
        required = _object(existing.get("required_status_checks") or {})
        checks = required.get("checks")
        kept = [
            {"context": _object(check).get("context"), "app_id": _object(check).get("app_id")}
            for check in (checks if isinstance(checks, list) else [])
            if _object(check).get("context") != RELEASE_CHECK_NAME
        ]
        reviews = _object(existing.get("required_pull_request_reviews") or {})
        restrictions = _object(existing.get("restrictions") or {})
        return {
            "required_status_checks": {
                "strict": required.get("strict") is True,
                "checks": [*kept, {"context": RELEASE_CHECK_NAME, "app_id": int(self._app_id)}],
            },
            "enforce_admins": True,
            # The human approval lives in Pono; the code host only requires a change request.
            "required_pull_request_reviews": {
                "required_approving_review_count": reviews.get(
                    "required_approving_review_count", 0
                ),
                "dismiss_stale_reviews": reviews.get("dismiss_stale_reviews", False),
                "require_code_owner_reviews": reviews.get("require_code_owner_reviews", False),
            },
            "restrictions": {
                "users": _names(restrictions, "users", "login"),
                "teams": _names(restrictions, "teams", "slug"),
                "apps": _names(restrictions, "apps", "slug"),
            }
            if restrictions
            else None,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }

    @staticmethod
    def _refusal(response: httpx.Response) -> None:
        message = str(_object(response.json()).get("message", "")).lower()
        if _PLAN_REFUSAL in message:
            raise ProtectionRefusedError("protection.unavailable_on_plan")
        raise ProtectionRefusedError("protection.permission_missing")

    async def _check_write(
        self, installation_id: str, repository: str, payload: JsonObject
    ) -> None:
        """The first bounded write: one check run named `pono/release`, nothing else."""

        if not _REPOSITORY.match(repository) or payload.get("name") != RELEASE_CHECK_NAME:
            raise ForbiddenWriteError("only the pono/release check can be written")
        await self._request(
            installation_id, "POST", f"/repos/{repository}/check-runs", json=payload
        )

    async def _protection_write(
        self, installation_id: str, repository: str, branch: str, payload: JsonObject
    ) -> None:
        """The second bounded write: the protection rule of one branch, nothing else (FR-015)."""

        if not _REPOSITORY.match(repository) or not branch or is_proposal_branch(branch):
            raise ForbiddenWriteError("only a production branch protection can be written")
        response = await self._request(
            installation_id,
            "PUT",
            f"/repos/{repository}/branches/{quote(branch)}/protection",
            json=payload,
            allow={403, 404, 422},
        )
        if response.status_code in {403, 404}:
            self._refusal(response)
        if response.status_code == 422:
            raise ProviderUnavailableError("code host refused the protection rule")

    # --- the only write path on branches -------------------------------------------------------

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
