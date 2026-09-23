"""Pre-fill a Pono manifest from an existing format and what the providers detected (FR-018).

Detection only completes: a value read from the repository is never overwritten by a guess.
"""

from pono_api.application.ports import Detection, ManifestDraft, RepositoryInfo
from pono_api.domain.manifest import (
    ManifestDatabase,
    ManifestEnvironment,
    ProjectManifest,
    ProviderRef,
)
from pono_api.domain.projects import EnvironmentKind


def _merge(environments: list[ManifestEnvironment], detection: Detection) -> None:
    found = detection.environment
    reference = ProviderRef(provider=detection.provider, ref=found.ref)
    if any(environment.hosting == reference for environment in environments):
        return
    for index, environment in enumerate(environments):
        branch_fits = environment.branch is None or found.branch in (None, environment.branch)
        if environment.kind is found.kind and environment.hosting is None and branch_fits:
            environments[index] = environment.model_copy(
                update={
                    "hosting": reference,
                    "url": environment.url or found.url,
                    "branch": environment.branch or found.branch,
                }
            )
            return
    environments.append(
        ManifestEnvironment(kind=found.kind, branch=found.branch, url=found.url, hosting=reference)
    )


def prefill(
    repository: RepositoryInfo,
    draft: ManifestDraft | None,
    detections: list[Detection],
    database: ProviderRef | None,
) -> ProjectManifest:
    environments = list(draft.environments) if draft else []
    for detection in detections:
        _merge(environments, detection)
    if not environments:
        environments = [
            ManifestEnvironment(kind=EnvironmentKind.PRODUCTION, branch=repository.default_branch)
        ]

    manifest_database = draft.database if draft else None
    if manifest_database is None and database is not None:
        manifest_database = ManifestDatabase(
            provider=database.provider,
            ref=database.ref,
            branches=draft.database_branches if draft else None,
        )

    return ProjectManifest.model_validate(
        {
            "schemaVersion": 1,
            "name": draft.name if draft else repository.full_name.split("/")[-1],
            "environments": environments,
            "database": manifest_database,
            "importedFrom": draft.source if draft else "provider-detection",
        }
    )


__all__ = ["prefill"]
