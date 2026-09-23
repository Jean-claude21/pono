"""Reader for the Pono manifest itself, `.pono/project.json`, the source of truth once merged."""

from pono_api.domain.manifest import ProjectManifest, parse_manifest
from pono_api.domain.projects import MANIFEST_PATH

PATH = MANIFEST_PATH


def read(content: str) -> ProjectManifest:
    """Raises `ManifestInvalidError` when the file breaks the schema."""

    return parse_manifest(content)


__all__ = ["PATH", "read"]
