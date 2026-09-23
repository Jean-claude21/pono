"""The Pono project manifest, `.pono/project.json` (D-003, contracts/manifest.schema.json).

It holds identifiers only, never secrets. The model mirrors the JSON schema exactly: unknown keys
are refused, so a manifest this model accepts is one the schema accepts.
"""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pono_api.domain.projects import EnvironmentKind

# Kept verbatim (no normalization), so a manifest round-trips unchanged.
Url = Annotated[str, Field(pattern=r"^https?://\S+$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProviderRef(_Strict):
    provider: Annotated[str, Field(min_length=1)]
    ref: Annotated[str, Field(min_length=1)]


class ManifestEnvironment(_Strict):
    kind: EnvironmentKind
    branch: str | None = None
    url: Url | None = None
    hosting: ProviderRef | None = None


class ManifestDatabase(ProviderRef):
    branches: dict[str, str] | None = None


ImportedFrom = Literal["studio-project-yaml", "fluxio", "livio", "provider-detection"]


class ProjectManifest(_Strict):
    schema_version: Literal[1] = Field(alias="schemaVersion")
    name: Annotated[str, Field(min_length=1)]
    environments: Annotated[list[ManifestEnvironment], Field(min_length=1)]
    database: ManifestDatabase | None = None
    imported_from: ImportedFrom | None = Field(None, alias="importedFrom")

    def to_json(self) -> str:
        """Canonical file content: schema keys, no nulls, stable indentation."""

        payload = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


class ManifestInvalidError(ValueError):
    """The file exists but is not a valid Pono manifest."""


def parse_manifest(content: str) -> ProjectManifest:
    try:
        return ProjectManifest.model_validate_json(content)
    except ValidationError as error:
        raise ManifestInvalidError("manifest does not match schema version 1") from error


__all__ = [
    "ImportedFrom",
    "ManifestDatabase",
    "ManifestEnvironment",
    "ManifestInvalidError",
    "ProjectManifest",
    "ProviderRef",
    "parse_manifest",
]
