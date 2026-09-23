"""Reader for Livio's `stack.hcl`.

Only the few attributes Pono needs are read: the project name, the hosting provider, the database
provider and its branch names. Livio stores no provider identifiers in the file, so detection
completes them.
"""

import re

from pono_api.application.ports import ManifestDraft, RepositoryInfo
from pono_api.domain.manifest import ManifestEnvironment
from pono_api.domain.projects import EnvironmentKind

PATH = "stack.hcl"
_TOKEN = re.compile(r'(\w+)\s*=\s*"([^"]*)"|(\w+)\s*\{|(\})')
_BRANCH_KINDS = {"prod": EnvironmentKind.PRODUCTION.value, "dev": EnvironmentKind.DEVELOPMENT.value}


def _attributes(content: str) -> dict[str, str]:
    """Flatten `block { key = "value" }` into `block.key` → value, ignoring comments."""

    lines = [line.split("#", 1)[0] for line in content.splitlines()]
    path: list[str] = []
    values: dict[str, str] = {}
    for match in _TOKEN.finditer("\n".join(lines)):
        key, value, block, closing = match.groups()
        if block:
            path.append(block)
        elif closing:
            if path:
                path.pop()
        elif key:
            values[".".join([*path, key])] = value
    return values


def read(content: str, repository: RepositoryInfo) -> ManifestDraft | None:
    values = _attributes(content)
    if "livio" not in values:
        return None
    name = values.get("project.name") or repository.full_name.split("/")[-1]
    environments = [
        ManifestEnvironment(kind=EnvironmentKind.PRODUCTION, branch=repository.default_branch)
    ]
    branches = {
        _BRANCH_KINDS[key.rsplit(".", 1)[1]]: value
        for key, value in values.items()
        if key.startswith("database.branches.")
        and key.rsplit(".", 1)[1] in _BRANCH_KINDS
        and "{" not in value
    }
    return ManifestDraft(
        source="livio",
        name=name,
        environments=environments,
        database_provider=values.get("database.provider"),
        database_branches=branches or None,
    )


__all__ = ["PATH", "read"]
