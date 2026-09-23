"""Manifest readers: the Pono manifest, and the formats Pono pre-fills it from (research R-06)."""

from collections.abc import Callable

from pono_api.application.ports import Detection, ManifestDraft, RepositoryInfo
from pono_api.domain.manifest import ProjectManifest, ProviderRef
from pono_api.infrastructure.manifests import fluxio, livio, studio_project_yaml
from pono_api.infrastructure.manifests.prefill import prefill

Reader = Callable[[str, RepositoryInfo], ManifestDraft | None]

# Order of precedence: the studio manifest, then Fluxio, then Livio.
READERS: tuple[tuple[str, Reader], ...] = (
    (studio_project_yaml.PATH, studio_project_yaml.read),
    (fluxio.PATH, fluxio.read),
    (livio.PATH, livio.read),
)


class RepositoryManifests:
    """The `ManifestReader` port over the readers of this package."""

    @property
    def legacy_paths(self) -> tuple[str, ...]:
        return tuple(path for path, _ in READERS)

    def read(self, path: str, content: str, repository: RepositoryInfo) -> ManifestDraft | None:
        reader = dict(READERS).get(path)
        return reader(content, repository) if reader else None

    def prefill(
        self,
        repository: RepositoryInfo,
        draft: ManifestDraft | None,
        detections: list[Detection],
        database: ProviderRef | None,
    ) -> ProjectManifest:
        return prefill(repository, draft, detections, database)


__all__ = ["READERS", "RepositoryManifests"]
