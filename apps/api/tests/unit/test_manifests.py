"""T029 — manifest readers and pre-fill, against contracts/manifest.schema.json (FR-015, FR-018).

The fixtures are the real formats found in the author's repositories (research R-06).
"""

import json
from pathlib import Path

import pytest

from pono_api.application.ports import DetectedEnvironment, Detection, RepositoryInfo
from pono_api.domain.manifest import (
    ManifestInvalidError,
    ProjectManifest,
    ProviderRef,
    parse_manifest,
)
from pono_api.domain.projects import EnvironmentKind
from pono_api.infrastructure.manifests import RepositoryManifests, fluxio, livio, pono
from pono_api.infrastructure.manifests import studio_project_yaml as studio
from pono_api.infrastructure.manifests.prefill import prefill

pytestmark = pytest.mark.unit

SCHEMA = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-project-workshop"
    / "contracts"
    / "manifest.schema.json"
)
LECTIO = RepositoryInfo("Jean-claude21/lectio-reads", "main")
LIVIO = RepositoryInfo("Jean-claude21/livio", "main")
NETTIO = RepositoryInfo("Jean-claude21/nettio", "main")

FLUXIO_JSON = json.dumps(
    {
        "fluxioVersion": 1,
        "slug": "lectio-reads",
        "github": {
            "repo": "Jean-claude21/lectio-reads",
            "defaultBranch": "main",
            "devBranch": "dev",
        },
        "neon": {
            "projectId": "royal-mouse-54581135",
            "branches": {"main": "br-falling-math", "dev": "br-winter-glitter"},
        },
        "netlify": {"siteId": "b74309b5", "url": "https://lectio-reads.netlify.app"},
        "coolify": {
            "projectUuid": "gdsm",
            "environmentUuid": "xeao",
            "applicationUuid": "sywgalt1",
            "devUrl": "https://sywgalt1.vttlife.com",
        },
    }
)

LIVIO_HCL = """
livio = "1"

# The manifest, read by the scripts.
project {
  name = "livio"
}

host {
  provider = "netlify"         # netlify or coolify
}

database {
  provider = "neon"
  orm      = "drizzle"
  branches {
    dev     = "dev"
    preview = "preview/{git.branch}"
    prod    = "main"
  }
}
"""

STUDIO_YAML = """
# Exploration output.
name: nettio
surfaces: [supabase, backend, web]
technos:
  backend: fastapi
"""


def test_fluxio_manifest_names_production_development_and_database() -> None:
    draft = fluxio.read(FLUXIO_JSON, LECTIO)

    assert draft is not None
    assert draft.source == "fluxio"
    assert draft.name == "lectio-reads"
    production, development = draft.environments
    assert production.kind is EnvironmentKind.PRODUCTION
    assert production.branch == "main"
    assert production.url == "https://lectio-reads.netlify.app"
    assert production.hosting == ProviderRef(provider="netlify", ref="b74309b5")
    assert development.kind is EnvironmentKind.DEVELOPMENT
    assert development.branch == "dev"
    assert development.hosting == ProviderRef(provider="coolify", ref="sywgalt1")
    assert draft.database is not None
    assert draft.database.ref == "royal-mouse-54581135"
    assert draft.database.branches == {"production": "main", "development": "dev"}


@pytest.mark.parametrize("content", ["not json", "[]", '{"slug": "x"}'])
def test_fluxio_reader_ignores_other_files(content: str) -> None:
    assert fluxio.read(content, LECTIO) is None


def test_fluxio_without_resources_keeps_only_the_name() -> None:
    draft = fluxio.read('{"fluxioVersion": 1}', LECTIO)
    assert draft is not None
    assert draft.name == "lectio-reads"
    assert draft.environments == []
    assert draft.database is None


def test_livio_stack_names_the_database_without_its_reference() -> None:
    draft = livio.read(LIVIO_HCL, LIVIO)

    assert draft is not None
    assert draft.source == "livio"
    assert draft.name == "livio"
    assert [environment.kind for environment in draft.environments] == [EnvironmentKind.PRODUCTION]
    assert draft.database is None
    assert draft.database_provider == "neon"
    # Templated branch names cannot be resolved ahead of time and are left out.
    assert draft.database_branches == {"development": "dev", "production": "main"}


def test_livio_reader_ignores_files_without_its_marker() -> None:
    assert livio.read('project { name = "x" }', LIVIO) is None


def test_studio_project_yaml_gives_only_a_name() -> None:
    draft = studio.read(STUDIO_YAML, NETTIO)
    assert draft is not None
    assert (draft.source, draft.name, draft.environments) == ("studio-project-yaml", "nettio", [])


@pytest.mark.parametrize("content", ["name: [unclosed", "- a list", "surfaces: [web]"])
def test_studio_reader_ignores_unusable_yaml(content: str) -> None:
    assert studio.read(content, NETTIO) is None


def test_repository_manifests_dispatch_by_path_in_order_of_precedence() -> None:
    manifests = RepositoryManifests()
    assert manifests.legacy_paths == ("project.yaml", ".fluxio/project.json", "stack.hcl")
    assert manifests.read("stack.hcl", LIVIO_HCL, LIVIO) is not None
    assert manifests.read("unknown.toml", "", LIVIO) is None


def test_prefill_completes_a_draft_with_detected_hosting_and_database() -> None:
    draft = livio.read(LIVIO_HCL, LIVIO)
    detected = [
        Detection(
            "netlify",
            DetectedEnvironment(
                EnvironmentKind.PRODUCTION, "a1caca2e", "https://livio-app.netlify.app", "main"
            ),
        )
    ]

    manifest = prefill(LIVIO, draft, detected, ProviderRef(provider="neon", ref="flat-cell"))

    assert manifest.imported_from == "livio"
    (production,) = manifest.environments
    assert production.hosting == ProviderRef(provider="netlify", ref="a1caca2e")
    assert production.url == "https://livio-app.netlify.app"
    assert manifest.database is not None
    assert (manifest.database.provider, manifest.database.ref) == ("neon", "flat-cell")
    assert manifest.database.branches == {"development": "dev", "production": "main"}


def test_prefill_never_overwrites_what_the_repository_says() -> None:
    draft = fluxio.read(FLUXIO_JSON, LECTIO)
    detected = [
        Detection("netlify", DetectedEnvironment(EnvironmentKind.PRODUCTION, "b74309b5")),
        Detection(
            "coolify",
            DetectedEnvironment(EnvironmentKind.PRODUCTION, "other-app", "https://x.test", "main"),
        ),
    ]

    manifest = prefill(LECTIO, draft, detected, ProviderRef(provider="neon", ref="ignored"))

    assert [env.hosting.ref for env in manifest.environments if env.hosting] == [
        "b74309b5",
        "sywgalt1",
        "other-app",
    ]
    assert manifest.database is not None
    assert manifest.database.ref == "royal-mouse-54581135"


def test_prefill_from_detection_alone_uses_the_repository_name() -> None:
    detected = [
        Detection(
            "coolify",
            DetectedEnvironment(
                EnvironmentKind.DEVELOPMENT, "gl3ouwtc", "https://nettio.vttlife.com", "dev"
            ),
        )
    ]

    manifest = prefill(NETTIO, None, detected, None)

    assert manifest.name == "nettio"
    assert manifest.imported_from == "provider-detection"
    assert manifest.environments[0].kind is EnvironmentKind.DEVELOPMENT
    assert manifest.database is None


def test_prefill_with_nothing_found_still_names_production() -> None:
    manifest = prefill(NETTIO, None, [], None)
    (production,) = manifest.environments
    assert (production.kind, production.branch, production.hosting) == (
        EnvironmentKind.PRODUCTION,
        "main",
        None,
    )


def test_manifest_json_round_trips_and_holds_no_null() -> None:
    manifest = prefill(LECTIO, fluxio.read(FLUXIO_JSON, LECTIO), [], None)
    content = manifest.to_json()

    assert "null" not in content
    assert json.loads(content)["schemaVersion"] == 1
    assert pono.read(content) == manifest


@pytest.mark.parametrize(
    "payload",
    [
        {"schemaVersion": 2, "name": "x", "environments": [{"kind": "production"}]},
        {"schemaVersion": 1, "name": "x", "environments": []},
        {"schemaVersion": 1, "name": "", "environments": [{"kind": "production"}]},
        {"schemaVersion": 1, "name": "x", "environments": [{"kind": "staging"}]},
        {"schemaVersion": 1, "name": "x", "environments": [{"kind": "production"}], "secret": 1},
        {
            "schemaVersion": 1,
            "name": "x",
            "environments": [{"kind": "production", "url": "not a url"}],
        },
    ],
)
def test_invalid_manifests_are_refused(payload: dict[str, object]) -> None:
    with pytest.raises(ManifestInvalidError):
        parse_manifest(json.dumps(payload))


def _properties(schema: dict[str, object], definitions: dict[str, object]) -> dict[str, object]:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        schema = definitions[reference.rsplit("/", 1)[-1]]  # type: ignore[assignment]
    for option in schema.get("anyOf", []):  # type: ignore[attr-defined]
        if isinstance(option, dict) and option.get("type") != "null":
            return _properties(option, definitions)
    return schema.get("properties", {})  # type: ignore[return-value]


def test_model_mirrors_the_contract_schema() -> None:
    """Same keys at every level, and unknown keys refused, as the JSON schema demands."""

    contract = json.loads(SCHEMA.read_text(encoding="utf-8"))
    model = ProjectManifest.model_json_schema(by_alias=True)
    definitions = model.get("$defs", {})

    assert set(model["properties"]) == set(contract["properties"])
    assert set(model["required"]) == set(contract["required"])
    environment = _properties(model["properties"]["environments"]["items"], definitions)
    assert set(environment) == set(contract["properties"]["environments"]["items"]["properties"])
    database = _properties(model["properties"]["database"], definitions)
    assert set(database) == set(contract["properties"]["database"]["properties"])
    release = _properties(model["properties"]["release"], definitions)
    assert set(release) == set(contract["properties"]["release"]["properties"])
    assert model.get("additionalProperties") is False


def test_the_release_section_is_optional_and_strict() -> None:
    """T005 — declarations the release guards read, written in the repository (002 FR-008)."""

    base = {
        "schemaVersion": 1,
        "name": "x",
        "environments": [{"kind": "production", "branch": "main"}],
    }
    assert parse_manifest(json.dumps(base)).release is None
    declared = parse_manifest(
        json.dumps(
            {
                **base,
                "release": {
                    "migrations": ["drizzle"],
                    "exampleFiles": [".env.example"],
                    "declaredDestructions": [
                        {"file": "drizzle/0007_drop.sql", "operation": "drop_column"}
                    ],
                },
            }
        )
    )
    assert declared.release is not None
    assert declared.release.migrations == ["drizzle"]
    assert declared.production_branch == "main"
    assert json.loads(declared.to_json())["release"]["exampleFiles"] == [".env.example"]
    for release in (
        {"declaredDestructions": [{"file": "a.sql", "operation": "drop_everything"}]},
        {"migrations": ["drizzle"], "skipGuards": True},
    ):
        with pytest.raises(ManifestInvalidError):
            parse_manifest(json.dumps({**base, "release": release}))
