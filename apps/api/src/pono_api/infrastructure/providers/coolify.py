"""Coolify adapter for the hosting port (ported from KYA-Platform's Coolify adapter).

It reads applications linked to a repository, their deployments, their previews, their status and
their public address. Its one write brings production back to an earlier image (002 R-08, D-016);
Pono never deploys new code through it.
"""

from urllib.parse import quote, urlsplit

import httpx

from pono_api.application.ports import (
    DeploymentRecord,
    DetectedEnvironment,
    HostedEnvironment,
    KeyUse,
    PreviewState,
    RollbackUnsupportedError,
)
from pono_api.domain.projects import DeploymentStatus, EnvironmentKind, ResourceStatus
from pono_api.domain.quotas import QuotaReading
from pono_api.infrastructure.providers.http import (
    JsonObject,
    KeyedClient,
    as_list,
    as_object,
    same_repository,
    text,
    timestamp,
)


def deployment_status(status: str | None) -> DeploymentStatus:
    normalized = (status or "").lower().replace("-", "_")
    if normalized == "finished":
        return DeploymentStatus.SUCCEEDED
    if normalized == "failed":
        return DeploymentStatus.FAILED
    if normalized in {"queued", "in_progress", "pending"} or "progress" in normalized:
        return DeploymentStatus.BUILDING
    return DeploymentStatus.CANCELLED


def public_url(fqdn: str | None) -> str | None:
    """Coolify lists every domain in one comma-separated field; the first one is the main one."""

    if not fqdn:
        return None
    first = fqdn.split(",")[0].strip()
    return first or None


def preview_url(application: JsonObject, change_number: int) -> str | None:
    """Coolify builds a preview address from the application's template and main domain."""

    main = public_url(text(application, "fqdn"))
    if main is None:
        return None
    parts = urlsplit(main)
    template = text(application, "preview_url_template") or "{{pr_id}}.{{domain}}"
    host = template.replace("{{pr_id}}", str(change_number)).replace(
        "{{domain}}", parts.hostname or ""
    )
    return f"{parts.scheme or 'https'}://{host}"


def _deployment(item: JsonObject) -> DeploymentRecord | None:
    reference, started = text(item, "deployment_uuid"), timestamp(item.get("created_at"))
    if reference is None or started is None:
        return None
    status = deployment_status(text(item, "status"))
    return DeploymentRecord(
        external_ref=reference,
        status=status,
        started_at=started,
        finished_at=None
        if status is DeploymentStatus.BUILDING
        else timestamp(item.get("updated_at")),
        commit_sha=text(item, "commit"),
    )


class CoolifyHosting:
    def __init__(
        self,
        endpoint: str,
        token: str,
        on_use: KeyUse,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._client = KeyedClient(
            f"{self._endpoint}/api/v1", token, on_use, provider="coolify", transport=transport
        )

    async def verify(self) -> str:
        team = as_object(await self._client.get("/teams/current", "verify_team"))
        host = urlsplit(self._endpoint).hostname or self._endpoint
        return f"{host}/{team.get('id', 'team')}"

    async def read_quotas(self) -> list[QuotaReading]:
        """A server of one's own has no plan quota: nothing to read, nothing invented."""

        return []

    async def detect(
        self, repository: str, name: str, default_branch: str
    ) -> list[DetectedEnvironment]:
        del name
        applications = [
            as_object(item)
            for item in as_list(await self._client.get("/applications", "list_applications"))
        ]
        detected: list[DetectedEnvironment] = []
        for application in applications:
            reference = text(application, "uuid")
            if reference is None or not same_repository(
                text(application, "git_repository"), repository
            ):
                continue
            branch = text(application, "git_branch")
            detected.append(
                DetectedEnvironment(
                    kind=EnvironmentKind.PRODUCTION
                    if branch == default_branch
                    else EnvironmentKind.DEVELOPMENT,
                    ref=reference,
                    url=public_url(text(application, "fqdn")),
                    branch=branch,
                )
            )
        return detected

    async def read_environment(
        self, ref: str, kind: EnvironmentKind, branch: str | None
    ) -> HostedEnvironment:
        del kind, branch
        application = await self._client.get(
            f"/applications/{quote(ref)}", "read_application", allow_missing=True
        )
        if application is None:
            return HostedEnvironment(status=ResourceStatus.MISSING)
        history = as_object(
            await self._client.get(
                f"/deployments/applications/{quote(ref)}?skip=0&take=10", "read_deployments"
            )
        )
        records = [
            record
            for item in as_list(history.get("deployments"))
            if (record := _deployment(as_object(item))) is not None
        ]
        records.sort(key=lambda record: record.started_at, reverse=True)
        live = next((r for r in records if r.status is DeploymentStatus.SUCCEEDED), None)
        return HostedEnvironment(
            status=ResourceStatus.FOUND,
            url=public_url(text(as_object(application), "fqdn")),
            deployments=tuple(records),
            live_commit=live.commit_sha if live else None,
        )

    async def find_preview(self, ref: str, change_number: int, head_sha: str) -> PreviewState:
        """The preview deployment of this change at this commit (002 research R-05)."""

        application = await self._client.get(
            f"/applications/{quote(ref)}", "read_application", allow_missing=True
        )
        if application is None:
            return PreviewState("absent")
        history = as_object(
            await self._client.get(
                f"/deployments/applications/{quote(ref)}?skip=0&take=30", "read_deployments"
            )
        )
        own = [
            as_object(item)
            for item in as_list(history.get("deployments"))
            if str(as_object(item).get("pull_request_id")) == str(change_number)
            and text(as_object(item), "commit") == head_sha
        ]
        if not own:
            return PreviewState("absent")
        latest = max(own, key=lambda item: text(item, "created_at") or "")
        status = deployment_status(text(latest, "status"))
        started = timestamp(latest.get("created_at"))
        if status is DeploymentStatus.SUCCEEDED:
            url = preview_url(as_object(application), change_number)
            return PreviewState("ready", url, started)
        if status is DeploymentStatus.BUILDING:
            return PreviewState("building", None, started)
        return PreviewState("failed", None, started)

    async def rollback(self, ref: str, target: DeploymentRecord) -> str:
        """Run the image of an earlier commit again, if the server still keeps it."""

        if target.commit_sha is None:
            raise RollbackUnsupportedError("the target deployment names no commit")
        images = as_object(
            await self._client.get(f"/applications/{quote(ref)}/rollback-images", "read_images")
        )
        tags = {text(as_object(image), "tag") for image in as_list(images.get("images"))}
        if target.commit_sha not in tags:
            raise RollbackUnsupportedError("the server no longer keeps this image")
        queued = await self._client.post(
            f"/applications/{quote(ref)}/rollback", "rollback", {"commit": target.commit_sha}
        )
        return text(as_object(queued), "deployment_uuid") or target.commit_sha


__all__ = ["CoolifyHosting", "deployment_status", "public_url"]
