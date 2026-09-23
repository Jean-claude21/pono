"""Reader for Fluxio's `.fluxio/project.json`: one hosted production, one development app."""

import json
from typing import cast

from pono_api.application.ports import ManifestDraft, RepositoryInfo
from pono_api.domain.manifest import ManifestDatabase, ManifestEnvironment, ProviderRef
from pono_api.domain.projects import EnvironmentKind

PATH = ".fluxio/project.json"
JsonObject = dict[str, object]


def _section(payload: JsonObject, key: str) -> JsonObject:
    value = payload.get(key)
    return cast(JsonObject, value) if isinstance(value, dict) else {}


def _text(payload: JsonObject, key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None


def read(content: str, repository: RepositoryInfo) -> ManifestDraft | None:
    try:
        payload = json.loads(content)
    except ValueError:
        return None
    if not isinstance(payload, dict) or "fluxioVersion" not in payload:
        return None
    payload = cast(JsonObject, payload)
    code = _section(payload, "github")
    default_branch = _text(code, "defaultBranch") or repository.default_branch
    dev_branch = _text(code, "devBranch")

    environments: list[ManifestEnvironment] = []
    site = _section(payload, "netlify")
    if site_id := _text(site, "siteId"):
        environments.append(
            ManifestEnvironment(
                kind=EnvironmentKind.PRODUCTION,
                branch=default_branch,
                url=_text(site, "url"),
                hosting=ProviderRef(provider="netlify", ref=site_id),
            )
        )
    application = _section(payload, "coolify")
    if application_id := _text(application, "applicationUuid"):
        environments.append(
            ManifestEnvironment(
                kind=EnvironmentKind.DEVELOPMENT,
                branch=dev_branch,
                url=_text(application, "devUrl"),
                hosting=ProviderRef(provider="coolify", ref=application_id),
            )
        )

    database: ManifestDatabase | None = None
    neon = _section(payload, "neon")
    if project_id := _text(neon, "projectId"):
        # Fluxio keys database branches by git branch; the Pono manifest keys them by environment.
        git_branches = _section(neon, "branches")
        branches = {
            kind: branch
            for kind, branch in (
                (EnvironmentKind.PRODUCTION.value, default_branch),
                (EnvironmentKind.DEVELOPMENT.value, dev_branch),
            )
            if branch and branch in git_branches
        }
        database = ManifestDatabase(provider="neon", ref=project_id, branches=branches or None)

    return ManifestDraft(
        source="fluxio",
        name=_text(payload, "slug") or repository.full_name.split("/")[-1],
        environments=environments,
        database=database,
    )


__all__ = ["PATH", "read"]
