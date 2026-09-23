"""Reader for the studio's `project.yaml`: a name, nothing more that Pono can trust.

It names no site or application, so every environment comes from provider detection.
"""

import yaml

from pono_api.application.ports import ManifestDraft, RepositoryInfo

PATH = "project.yaml"


def read(content: str, repository: RepositoryInfo) -> ManifestDraft | None:
    del repository
    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError:
        return None
    if not isinstance(payload, dict):
        return None
    name = payload.get("name")
    if not isinstance(name, str) or not name:
        return None
    return ManifestDraft(source="studio-project-yaml", name=name)


__all__ = ["PATH", "read"]
