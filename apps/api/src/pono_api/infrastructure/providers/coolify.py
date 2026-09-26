"""Coolify adapter for the hosting port (ported from KYA-Platform's Coolify adapter).

It reads applications linked to a repository, their deployments, their previews, their status and
their public address. It writes twice: bringing production back to an earlier image (002 R-08,
D-016), and the development runtime's own application — create, start, stop, delete — in its own
"Pono runtimes" project (004, D-019). It never deploys a project's production through it.
"""

import re
import secrets
from urllib.parse import quote, urlsplit

import httpx

from pono_api.application.ports import (
    DeploymentRecord,
    DetectedEnvironment,
    HostedEnvironment,
    HostRuntimeStatus,
    KeyUse,
    PreviewState,
    ProviderUnavailableError,
    RollbackUnsupportedError,
    RuntimeHandle,
    RuntimeHostError,
    RuntimeSpec,
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

    # --- the runtime's application, and nothing else (004 research R-02, D-019) -----------------

    async def create_runtime(self, spec: RuntimeSpec) -> RuntimeHandle:
        server = await self._runtime_server(spec.near_ref)
        project = await self._runtime_project()
        key = as_object(
            await self._client.post(
                "/security/keys",
                "create_runtime_key",
                {
                    "name": f"pono-runtime-{spec.name}",
                    "description": "Read-only deploy key of a Pono development runtime",
                    "private_key": spec.private_key,
                },
            )
        )
        key_ref = text(key, "uuid")
        if key_ref is None:
            raise ProviderUnavailableError("coolify returned no key")
        url = runtime_url(spec.name, server)
        created = as_object(
            await self._client.post(
                "/applications/private-deploy-key",
                "create_runtime",
                {
                    "project_uuid": project,
                    "server_uuid": text(server, "uuid"),
                    "environment_name": RUNTIME_ENVIRONMENT,
                    "private_key_uuid": key_ref,
                    "git_repository": spec.clone_url,
                    "git_branch": spec.branch,
                    "build_pack": "dockerfile",
                    "dockerfile_location": RUNTIME_DOCKERFILE,
                    "ports_exposes": "3000",
                    "domains": url,
                    "name": f"pono-runtime-{spec.name}",
                    "description": "Pono development runtime",
                    "limits_memory": spec.memory,
                    "is_auto_deploy_enabled": False,
                    "instant_deploy": False,
                },
            )
        )
        reference = text(created, "uuid")
        if reference is None:
            raise ProviderUnavailableError("coolify returned no application")
        for key_name, value in sorted(spec.variables.items()):
            await self._client.post(
                f"/applications/{quote(reference)}/envs",
                "set_runtime_variable",
                {"key": key_name, "value": value, "is_preview": False, "is_literal": True},
            )
        return RuntimeHandle(ref=reference, url=url, key_ref=key_ref)

    async def start_runtime(self, ref: str) -> None:
        await self._client.post(f"/applications/{quote(ref)}/start", "start_runtime")

    async def stop_runtime(self, ref: str) -> None:
        await self._client.post(f"/applications/{quote(ref)}/stop", "stop_runtime")

    async def delete_runtime(self, ref: str, key_ref: str | None) -> None:
        await self._client.delete(
            f"/applications/{quote(ref)}?delete_configurations=true&delete_volumes=true"
            "&docker_cleanup=true",
            "delete_runtime",
        )
        if key_ref:
            await self._client.delete(f"/security/keys/{quote(key_ref)}", "delete_runtime_key")

    async def runtime_status(self, ref: str) -> HostRuntimeStatus:
        application = await self._client.get(
            f"/applications/{quote(ref)}", "read_runtime", allow_missing=True
        )
        if application is None:
            return "missing"
        status = (text(as_object(application), "status") or "").lower()
        if status.startswith("running"):
            return "running"
        history = as_object(
            await self._client.get(
                f"/deployments/applications/{quote(ref)}?skip=0&take=1", "read_runtime_deployments"
            )
        )
        latest = next(iter(as_list(history.get("deployments"))), None)
        deployment = deployment_status(text(as_object(latest), "status")) if latest else None
        if deployment is DeploymentStatus.BUILDING or status.startswith(("starting", "restarting")):
            return "starting"
        if deployment is DeploymentStatus.FAILED:
            return "failed"
        return "stopped"

    async def _runtime_server(self, near_ref: str | None) -> JsonObject:
        servers = [
            server
            for server in map(
                as_object, as_list(await self._client.get("/servers", "list_servers"))
            )
            if as_object(server.get("settings")).get("is_usable", True) is not False
        ]
        if near_ref is not None:
            application = as_object(
                await self._client.get(
                    f"/applications/{quote(near_ref)}", "read_application", allow_missing=True
                )
            )
            near = text(as_object(as_object(application.get("destination")).get("server")), "uuid")
            chosen = [server for server in servers if text(server, "uuid") == near]
            if chosen:
                return chosen[0]
        if len(servers) != 1:
            raise RuntimeHostError("runtime.server_ambiguous")
        return servers[0]

    async def _runtime_project(self) -> str:
        for project in map(
            as_object, as_list(await self._client.get("/projects", "list_projects"))
        ):
            if text(project, "name") == RUNTIME_PROJECT and (uuid := text(project, "uuid")):
                return uuid
        created = as_object(
            await self._client.post(
                "/projects",
                "create_runtime_project",
                {"name": RUNTIME_PROJECT, "description": "Development runtimes run by Pono"},
            )
        )
        uuid = text(created, "uuid")
        if uuid is None:
            raise ProviderUnavailableError("coolify returned no project")
        return uuid


RUNTIME_PROJECT = "Pono runtimes"
RUNTIME_ENVIRONMENT = "production"
RUNTIME_DOCKERFILE = "/.pono/runtime/Dockerfile"


def runtime_url(name: str, server: JsonObject) -> str:
    """`https://<name>-dev-<suffix>.<wildcard domain>`, or `<ip>.sslip.io` without one."""

    wildcard = text(as_object(server.get("settings")), "wildcard_domain")
    if wildcard:
        domain = urlsplit(wildcard if "//" in wildcard else f"//{wildcard}").hostname or ""
    else:
        domain = f"{text(server, 'ip') or '127.0.0.1'}.sslip.io"
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:40] or "project"
    return f"https://{slug}-dev-{secrets.token_hex(3)}.{domain}"


__all__ = ["CoolifyHosting", "deployment_status", "public_url", "runtime_url"]
