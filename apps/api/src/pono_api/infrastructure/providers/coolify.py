"""Coolify adapter for the hosting port, read-only (ported from KYA-Platform's Coolify adapter).

Pono never deploys through it: it reads applications linked to a repository, their deployments,
their status and their public address.
"""

from urllib.parse import quote, urlsplit

import httpx

from pono_api.application.ports import (
    DeploymentRecord,
    DetectedEnvironment,
    HostedEnvironment,
    KeyUse,
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
        return HostedEnvironment(
            status=ResourceStatus.FOUND,
            url=public_url(text(as_object(application), "fqdn")),
            deployments=tuple(records),
        )


__all__ = ["CoolifyHosting", "deployment_status", "public_url"]
