"""Netlify adapter for the hosting port: sites linked to a repository, deploys, previews."""

from urllib.parse import quote

import httpx

from pono_api.application.ports import (
    DeploymentRecord,
    DetectedEnvironment,
    HostedEnvironment,
    KeyUse,
    PreviewRecord,
    PreviewState,
    ProviderUnavailableError,
    RollbackUnsupportedError,
)
from pono_api.domain.projects import DeploymentStatus, EnvironmentKind, ResourceStatus
from pono_api.domain.quotas import LimitSource, Metric, QuotaReading
from pono_api.infrastructure.providers.http import (
    JsonObject,
    KeyedClient,
    as_list,
    as_object,
    same_repository,
    text,
    timestamp,
)

API_URL = "https://api.netlify.com/api/v1"
IN_PROGRESS = {
    "new",
    "pending_review",
    "accepted",
    "enqueued",
    "building",
    "uploading",
    "uploaded",
    "preparing",
    "prepared",
    "processing",
    "processed",
}
MAX_PREVIEWS = 5


def deployment_status(state: str | None) -> DeploymentStatus:
    if state == "ready":
        return DeploymentStatus.SUCCEEDED
    if state in {"error", "failed"}:
        return DeploymentStatus.FAILED
    if state in IN_PROGRESS:
        return DeploymentStatus.BUILDING
    return DeploymentStatus.CANCELLED


def _deployment(deploy: JsonObject) -> DeploymentRecord | None:
    reference, started = text(deploy, "id"), timestamp(deploy.get("created_at"))
    if reference is None or started is None:
        return None
    status = deployment_status(text(deploy, "state"))
    finished = timestamp(deploy.get("published_at")) or timestamp(deploy.get("updated_at"))
    return DeploymentRecord(
        external_ref=reference,
        status=status,
        started_at=started,
        finished_at=None if status is DeploymentStatus.BUILDING else finished,
        commit_sha=text(deploy, "commit_ref"),
        author=text(deploy, "committer"),
    )


class NetlifyHosting:
    def __init__(
        self,
        token: str,
        on_use: KeyUse,
        *,
        api_url: str = API_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = KeyedClient(api_url, token, on_use, provider="netlify", transport=transport)

    async def verify(self) -> str:
        accounts = as_list(await self._client.get("/accounts", "verify_account"))
        slugs = [text(as_object(account), "slug") for account in accounts]
        known = [slug for slug in slugs if slug]
        if not known:
            raise ProviderUnavailableError("netlify returned no account")
        return known[0]

    async def read_quotas(self) -> list[QuotaReading]:
        """Bandwidth of the account against its plan's allowance, both as Netlify states them."""

        account = await self.verify()
        usage = as_object(
            await self._client.get(f"/accounts/{quote(account)}/bandwidth", "read_bandwidth")
        )
        used, included = usage.get("used"), usage.get("included")
        start = timestamp(usage.get("period_start_date"))
        if not isinstance(used, int | float) or start is None:
            return []
        end = timestamp(usage.get("period_end_date"))
        return [
            QuotaReading(
                metric=Metric.HOSTING_BANDWIDTH_BYTES,
                used=float(used),
                limit=float(included) if isinstance(included, int | float) and included else None,
                limit_source=LimitSource.ACCOUNT_PLAN,
                period_start=start.date(),
                period_end=end.date() if end else None,
            )
        ]

    async def detect(
        self, repository: str, name: str, default_branch: str
    ) -> list[DetectedEnvironment]:
        sites = [as_object(site) for site in await self._all_sites()]
        linked = [
            site
            for site in sites
            if same_repository(text(as_object(site.get("build_settings")), "repo_url"), repository)
        ]
        if not linked:
            # A site deployed by hand has no repository link: accept only an unambiguous name.
            candidates = {name.lower(), f"{name.lower()}-app", f"{name.lower()}-web"}
            named = [site for site in sites if (text(site, "name") or "").lower() in candidates]
            linked = named if len(named) == 1 else []
        detected: list[DetectedEnvironment] = []
        for site in linked:
            reference = text(site, "id")
            if reference is None:
                continue
            branch = text(as_object(site.get("build_settings")), "repo_branch")
            detected.append(
                DetectedEnvironment(
                    kind=EnvironmentKind.PRODUCTION,
                    ref=reference,
                    url=text(site, "ssl_url") or text(site, "url"),
                    branch=branch or default_branch,
                )
            )
        return detected

    async def read_environment(
        self, ref: str, kind: EnvironmentKind, branch: str | None
    ) -> HostedEnvironment:
        site = await self._client.get(f"/sites/{ref}", "read_site", allow_missing=True)
        if site is None:
            return HostedEnvironment(status=ResourceStatus.MISSING)
        site_payload = as_object(site)
        deploys = [
            as_object(deploy)
            for deploy in as_list(
                await self._client.get(f"/sites/{ref}/deploys?per_page=30", "read_deploys")
            )
        ]
        if kind is EnvironmentKind.PRODUCTION:
            own = [deploy for deploy in deploys if text(deploy, "context") == "production"]
            url = text(site_payload, "ssl_url") or text(site_payload, "url")
            previews = self._previews(deploys)
        else:
            own = [
                deploy
                for deploy in deploys
                if text(deploy, "context") == "branch-deploy"
                and (branch is None or text(deploy, "branch") == branch)
            ]
            url = text(own[0], "deploy_ssl_url") if own else None
            previews = ()
        records = [record for deploy in own if (record := _deployment(deploy)) is not None]
        published = as_object(site_payload.get("published_deploy"))
        return HostedEnvironment(
            status=ResourceStatus.FOUND,
            url=url,
            deployments=tuple(records),
            previews=previews,
            # A restored deploy is published again without a new deploy: this is what is live.
            live_commit=text(published, "commit_ref")
            if kind is EnvironmentKind.PRODUCTION
            else None,
        )

    async def find_preview(self, ref: str, change_number: int, head_sha: str) -> PreviewState:
        """The deploy preview of this change at this commit (002 research R-05)."""

        deploys = [
            as_object(deploy)
            for deploy in as_list(
                await self._client.get(f"/sites/{ref}/deploys?per_page=50", "read_deploys")
            )
        ]
        own = [
            deploy
            for deploy in deploys
            if text(deploy, "context") == "deploy-preview"
            and str(deploy.get("review_id")) == str(change_number)
            and text(deploy, "commit_ref") == head_sha
        ]
        if not own:
            return PreviewState("absent")
        latest = max(own, key=lambda deploy: text(deploy, "created_at") or "")
        status = deployment_status(text(latest, "state"))
        started = timestamp(latest.get("created_at"))
        if status is DeploymentStatus.SUCCEEDED:
            return PreviewState("ready", text(latest, "deploy_ssl_url"), started)
        if status is DeploymentStatus.BUILDING:
            return PreviewState("building", None, started)
        return PreviewState("failed", None, started)

    async def rollback(self, ref: str, target: DeploymentRecord) -> str:
        """Publish an earlier production deploy again: Netlify keeps every deploy."""

        restored = await self._client.post(
            f"/sites/{ref}/deploys/{target.external_ref}/restore",
            "restore_deploy",
            allow_missing=True,
        )
        if restored is None:
            raise RollbackUnsupportedError("netlify no longer has this deploy")
        return text(as_object(restored), "id") or target.external_ref

    @staticmethod
    def _previews(deploys: list[JsonObject]) -> tuple[PreviewRecord, ...]:
        latest: dict[str, PreviewRecord] = {}
        for deploy in deploys:
            if text(deploy, "context") != "deploy-preview":
                continue
            opened, url = timestamp(deploy.get("created_at")), text(deploy, "deploy_ssl_url")
            if opened is None or url is None:
                continue
            key = str(deploy.get("review_id") or text(deploy, "branch") or text(deploy, "id"))
            if key in latest and latest[key].opened_at >= opened:
                continue
            latest[key] = PreviewRecord(
                external_ref=key,
                url=url,
                opened_at=opened,
                branch=text(deploy, "branch"),
                review_url=text(deploy, "review_url"),
            )
        ordered = sorted(latest.values(), key=lambda preview: preview.opened_at, reverse=True)
        return tuple(ordered[:MAX_PREVIEWS])

    async def _all_sites(self) -> list[object]:
        sites: list[object] = []
        page = 1
        while True:
            batch = as_list(
                await self._client.get(f"/sites?per_page=100&page={page}", "list_sites")
            )
            sites.extend(batch)
            if len(batch) < 100:
                return sites
            page += 1


__all__ = ["NetlifyHosting", "deployment_status"]
