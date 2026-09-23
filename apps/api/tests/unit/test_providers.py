"""Hosting and database adapters against the payload shapes their real APIs return.

Every call made with a permanent key is reported through `on_use` (FR-011, D-007).
"""

import json
from uuid import uuid4

import httpx
import pytest

from pono_api.application.ports import (
    ProviderAuthorizationError,
    ProviderUnavailableError,
    StoredConnection,
)
from pono_api.domain.projects import (
    ConnectionKind,
    DeploymentStatus,
    EnvironmentKind,
    ResourceStatus,
)
from pono_api.infrastructure.crypto import CredentialCipher
from pono_api.infrastructure.providers import coolify, netlify
from pono_api.infrastructure.providers.coolify import CoolifyHosting
from pono_api.infrastructure.providers.http import same_repository
from pono_api.infrastructure.providers.neon import NeonDatabase
from pono_api.infrastructure.providers.netlify import NetlifyHosting
from pono_api.infrastructure.providers.registry import ProviderRegistry, UnsupportedProviderError

pytestmark = pytest.mark.unit


class Api:
    def __init__(self, routes: dict[str, object]) -> None:
        self.routes = routes
        self.paths: list[str] = []
        self.authorizations: set[str] = set()

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        self.paths.append(path)
        self.authorizations.add(request.headers.get("authorization", ""))
        answer = self.routes.get(path)
        if isinstance(answer, int):
            return httpx.Response(answer, json={})
        if answer is None:
            return httpx.Response(404, json={"message": "not found"})
        return httpx.Response(200, content=json.dumps(answer).encode())

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


LECTIO_SITE = {
    "id": "b743",
    "name": "lectio-reads",
    "ssl_url": "https://lectio-reads.netlify.app",
    "build_settings": {
        "repo_url": "https://github.com/Jean-claude21/lectio-reads",
        "repo_branch": "main",
    },
}
LIVIO_SITE = {
    "id": "a1ca",
    "name": "livio-app",
    "ssl_url": "https://livio-app.netlify.app",
    "build_settings": {},
}
DEPLOYS = [
    {
        "id": "d3",
        "state": "building",
        "context": "production",
        "branch": "main",
        "commit_ref": "c3",
        "created_at": "2026-09-20T10:00:00Z",
        "committer": "Jean-claude21",
    },
    {
        "id": "d2",
        "state": "ready",
        "context": "deploy-preview",
        "branch": "dev",
        "review_id": 1,
        "review_url": "https://github.com/Jean-claude21/lectio-reads/pull/1",
        "commit_ref": "c2",
        "created_at": "2026-09-14T20:13:48.457Z",
        "deploy_ssl_url": "https://deploy-preview-1--lectio-reads.netlify.app",
    },
    {
        "id": "d1",
        "state": "ready",
        "context": "production",
        "branch": "main",
        "commit_ref": "c1",
        "created_at": "2026-09-14T20:05:22.866Z",
        "published_at": "2026-09-14T20:05:50.416Z",
        "committer": "Jean-claude21",
    },
    {
        "id": "d0",
        "state": "ready",
        "context": "branch-deploy",
        "branch": "dev",
        "created_at": "2026-09-13T08:00:00Z",
        "deploy_ssl_url": "https://dev--lectio-reads.netlify.app",
    },
]


def recorder() -> tuple[list[str], object]:
    actions: list[str] = []
    return actions, actions.append


async def test_netlify_verify_returns_the_account_and_traces_the_use() -> None:
    api = Api({"/api/v1/accounts": [{"slug": "jean-claude21"}]})
    actions, on_use = recorder()
    adapter = NetlifyHosting("netlify-key", on_use, transport=api.transport)  # type: ignore[arg-type]

    assert await adapter.verify() == "jean-claude21"
    assert actions == ["verify_account"]
    assert api.authorizations == {"Bearer netlify-key"}


async def test_netlify_detects_a_linked_site_before_a_named_one() -> None:
    api = Api({"/api/v1/sites?per_page=100&page=1": [LIVIO_SITE, LECTIO_SITE]})
    adapter = NetlifyHosting("k", lambda _: None, transport=api.transport)

    (found,) = await adapter.detect("Jean-claude21/lectio-reads", "lectio-reads", "main")

    assert (found.kind, found.ref, found.url, found.branch) == (
        EnvironmentKind.PRODUCTION,
        "b743",
        "https://lectio-reads.netlify.app",
        "main",
    )


async def test_netlify_accepts_an_unambiguous_name_for_a_site_deployed_by_hand() -> None:
    api = Api({"/api/v1/sites?per_page=100&page=1": [LIVIO_SITE, LECTIO_SITE]})
    adapter = NetlifyHosting("k", lambda _: None, transport=api.transport)

    (found,) = await adapter.detect("Jean-claude21/livio", "livio", "main")
    assert found.ref == "a1ca"
    assert await adapter.detect("Jean-claude21/other", "other", "main") == []


async def test_netlify_reads_production_deployments_and_open_previews() -> None:
    api = Api(
        {"/api/v1/sites/b743": LECTIO_SITE, "/api/v1/sites/b743/deploys?per_page=30": DEPLOYS}
    )
    adapter = NetlifyHosting("k", lambda _: None, transport=api.transport)

    hosted = await adapter.read_environment("b743", EnvironmentKind.PRODUCTION, "main")

    assert hosted.status is ResourceStatus.FOUND
    assert hosted.url == "https://lectio-reads.netlify.app"
    assert [(d.external_ref, d.status) for d in hosted.deployments] == [
        ("d3", DeploymentStatus.BUILDING),
        ("d1", DeploymentStatus.SUCCEEDED),
    ]
    assert hosted.deployments[0].finished_at is None
    assert hosted.deployments[1].author == "Jean-claude21"
    (preview,) = hosted.previews
    assert preview.url == "https://deploy-preview-1--lectio-reads.netlify.app"
    assert preview.review_url == "https://github.com/Jean-claude21/lectio-reads/pull/1"


async def test_netlify_reads_a_branch_environment_from_its_branch_deploys() -> None:
    api = Api(
        {"/api/v1/sites/b743": LECTIO_SITE, "/api/v1/sites/b743/deploys?per_page=30": DEPLOYS}
    )
    adapter = NetlifyHosting("k", lambda _: None, transport=api.transport)

    hosted = await adapter.read_environment("b743", EnvironmentKind.DEVELOPMENT, "dev")

    assert hosted.url == "https://dev--lectio-reads.netlify.app"
    assert [d.external_ref for d in hosted.deployments] == ["d0"]
    assert hosted.previews == ()


async def test_netlify_reports_a_missing_site_and_a_refused_key() -> None:
    missing = NetlifyHosting("k", lambda _: None, transport=Api({}).transport)
    assert (await missing.read_environment("gone", EnvironmentKind.PRODUCTION, None)).status is (
        ResourceStatus.MISSING
    )
    refused = NetlifyHosting(
        "k", lambda _: None, transport=Api({"/api/v1/accounts": 401}).transport
    )
    with pytest.raises(ProviderAuthorizationError):
        await refused.verify()
    empty = NetlifyHosting("k", lambda _: None, transport=Api({"/api/v1/accounts": []}).transport)
    with pytest.raises(ProviderUnavailableError):
        await empty.verify()


@pytest.mark.parametrize(
    ("state", "status"),
    [
        ("ready", DeploymentStatus.SUCCEEDED),
        ("error", DeploymentStatus.FAILED),
        ("enqueued", DeploymentStatus.BUILDING),
        ("rejected", DeploymentStatus.CANCELLED),
        (None, DeploymentStatus.CANCELLED),
    ],
)
def test_netlify_deploy_states(state: str | None, status: DeploymentStatus) -> None:
    assert netlify.deployment_status(state) is status


APPLICATIONS = [
    {
        "uuid": "o2we",
        "name": "firmo-web",
        "git_repository": "Jean-claude21/firmo",
        "git_branch": "dev",
        "fqdn": "https://staging.vttlife.com",
    },
    {
        "uuid": "kybo",
        "name": "kya-platform-backend",
        "git_repository": "Jean-claude21/kya-platform",
        "git_branch": "main",
        "fqdn": "https://api.kya-platform.vttlife.com,https://kybo.vttlife.com",
    },
    {
        "uuid": "fprd",
        "name": "firmo-prod",
        "git_repository": "https://github.com/jean-claude21/firmo.git",
        "git_branch": "main",
        "fqdn": None,
    },
]


async def test_coolify_detects_applications_of_the_repository_by_branch() -> None:
    api = Api({"/api/v1/applications": APPLICATIONS})
    adapter = CoolifyHosting(
        "https://app.coolify.test", "k", lambda _: None, transport=api.transport
    )

    found = await adapter.detect("Jean-claude21/firmo", "firmo", "main")

    assert [(item.ref, item.kind, item.url) for item in found] == [
        ("o2we", EnvironmentKind.DEVELOPMENT, "https://staging.vttlife.com"),
        ("fprd", EnvironmentKind.PRODUCTION, None),
    ]


async def test_coolify_reads_an_application_and_its_deployments() -> None:
    api = Api(
        {
            "/api/v1/applications/kybo": APPLICATIONS[1],
            "/api/v1/deployments/applications/kybo?skip=0&take=10": {
                "count": 2,
                "deployments": [
                    {
                        "deployment_uuid": "old",
                        "status": "failed",
                        "commit": "c1",
                        "created_at": "2026-08-24T20:07:34.000000Z",
                        "updated_at": "2026-08-24T20:08:01.000000Z",
                    },
                    {
                        "deployment_uuid": "new",
                        "status": "in_progress",
                        "commit": "c2",
                        "created_at": "2026-09-01T10:00:00.000000Z",
                        "updated_at": "2026-09-01T10:00:05.000000Z",
                    },
                ],
            },
        }
    )
    actions, on_use = recorder()
    adapter = CoolifyHosting("https://app.coolify.test/", "k", on_use, transport=api.transport)  # type: ignore[arg-type]

    hosted = await adapter.read_environment("kybo", EnvironmentKind.PRODUCTION, "main")

    assert hosted.url == "https://api.kya-platform.vttlife.com"
    assert [(d.external_ref, d.status) for d in hosted.deployments] == [
        ("new", DeploymentStatus.BUILDING),
        ("old", DeploymentStatus.FAILED),
    ]
    assert hosted.deployments[0].finished_at is None
    assert actions == ["read_application", "read_deployments"]


async def test_coolify_verify_names_the_instance_and_team() -> None:
    api = Api({"/api/v1/teams/current": {"id": 7, "name": "Root"}})
    adapter = CoolifyHosting(
        "https://app.coolify.test", "k", lambda _: None, transport=api.transport
    )
    assert await adapter.verify() == "app.coolify.test/7"
    missing = CoolifyHosting(
        "https://app.coolify.test", "k", lambda _: None, transport=Api({}).transport
    )
    assert (await missing.read_environment("x", EnvironmentKind.PRODUCTION, None)).status is (
        ResourceStatus.MISSING
    )


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        ("finished", DeploymentStatus.SUCCEEDED),
        ("failed", DeploymentStatus.FAILED),
        ("queued", DeploymentStatus.BUILDING),
        ("cancelled-by-user", DeploymentStatus.CANCELLED),
    ],
)
def test_coolify_deployment_states(raw: str, status: DeploymentStatus) -> None:
    assert coolify.deployment_status(raw) is status


def test_coolify_public_url_is_the_first_domain() -> None:
    assert coolify.public_url(None) is None
    assert coolify.public_url(" , ") is None
    assert coolify.public_url("https://a.test,https://b.test") == "https://a.test"


async def test_neon_finds_a_project_by_exact_name_and_reads_its_branches() -> None:
    api = Api(
        {
            "/api/v2/users/me": {"id": "user-1"},
            "/api/v2/users/me/organizations": {"organizations": [{"id": "org-a"}, {"id": "org-b"}]},
            "/api/v2/projects?limit=100&org_id=org-a&search=livio": {
                "projects": [{"id": "flat-cell", "name": "livio"}, {"id": "x", "name": "livio-old"}]
            },
            "/api/v2/projects?limit=100&org_id=org-b&search=livio": {"projects": []},
            "/api/v2/projects/flat-cell": {"project": {"id": "flat-cell"}},
            "/api/v2/projects/flat-cell/branches": {
                "branches": [{"name": "main"}, {"name": "dev"}]
            },
        }
    )
    actions, on_use = recorder()
    adapter = NeonDatabase(
        "neon-key", on_use, api_url="https://neon.test/api/v2", transport=api.transport
    )  # type: ignore[arg-type]

    assert await adapter.verify() == "user-1"
    assert await adapter.find_project("livio") == "flat-cell"
    snapshot = await adapter.read_project("flat-cell")
    assert (snapshot.status, snapshot.branches) == (ResourceStatus.FOUND, ("main", "dev"))
    assert (await adapter.read_project("gone")).status is ResourceStatus.MISSING
    assert actions == [
        "verify_user",
        "list_organizations",
        "list_projects",
        "list_projects",
        "read_project",
        "read_branches",
        "read_project",
    ]


async def test_neon_does_not_guess_between_homonyms_and_reports_outages() -> None:
    api = Api(
        {
            "/api/v2/users/me/organizations": {"organizations": [{"id": "org-a"}]},
            "/api/v2/projects?limit=100&org_id=org-a&search=app": {
                "projects": [{"id": "a", "name": "app"}, {"id": "b", "name": "App"}]
            },
            "/api/v2/users/me": 500,
        }
    )
    adapter = NeonDatabase(
        "k", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )
    assert await adapter.find_project("app") is None
    with pytest.raises(ProviderUnavailableError):
        await adapter.verify()


async def test_network_failure_is_an_unavailable_provider() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    adapter = NeonDatabase("k", lambda _: None, transport=httpx.MockTransport(fail))
    with pytest.raises(ProviderUnavailableError):
        await adapter.verify()


async def test_non_json_answer_is_an_unavailable_provider() -> None:
    adapter = NeonDatabase(
        "k",
        lambda _: None,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>")),
    )
    with pytest.raises(ProviderUnavailableError):
        await adapter.verify()


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("https://github.com/Jean-claude21/firmo", True),
        ("https://github.com/jean-claude21/firmo.git", True),
        ("git@github.com:Jean-claude21/firmo.git", True),
        ("Jean-claude21/firmo", True),
        ("Jean-claude21/firmo-web", False),
        (None, False),
    ],
)
def test_repository_references_are_matched_exactly(reference: str | None, expected: bool) -> None:
    assert same_repository(reference, "Jean-claude21/firmo") is expected


def test_registry_builds_adapters_from_sealed_keys_only() -> None:
    cipher = CredentialCipher(CredentialCipher.generate_key())
    registry = ProviderRegistry(cipher)
    sealed = registry.seal("netlify-key")
    connection = StoredConnection(
        id=uuid4(),
        kind=ConnectionKind.HOSTING,
        provider="netlify",
        external_ref="acc",
        endpoint=None,
        secret_ciphertext=sealed,
        status="active",
    )

    assert b"netlify-key" not in sealed
    assert registry.supports(ConnectionKind.HOSTING, "coolify")
    assert not registry.supports(ConnectionKind.DATABASE, "supabase")
    assert isinstance(registry.hosting(connection, lambda _: None), NetlifyHosting)
    assert isinstance(
        registry.probe_hosting("coolify", "k", "https://app.coolify.test"), CoolifyHosting
    )
    assert isinstance(registry.probe_database("neon", "k", None), NeonDatabase)
    with pytest.raises(UnsupportedProviderError):
        registry.probe_hosting("coolify", "k", None)
    with pytest.raises(UnsupportedProviderError):
        registry.probe_hosting("vercel", "k", None)
    with pytest.raises(UnsupportedProviderError):
        registry.probe_database("supabase", "k", None)
    with pytest.raises(ProviderAuthorizationError):
        registry.database(
            StoredConnection(
                connection.id, ConnectionKind.DATABASE, "neon", "x", None, None, "revoked"
            ),
            lambda _: None,
        )
    foreign = ProviderRegistry(CredentialCipher(CredentialCipher.generate_key()))
    with pytest.raises(ProviderAuthorizationError):
        foreign.hosting(connection, lambda _: None)
    with pytest.raises(UnsupportedProviderError):
        ProviderRegistry(None).seal("k")


async def test_neon_accepts_an_organization_key() -> None:
    """An organization key has no user: `/users/me` answers 404, which is not an outage."""

    api = Api(
        {
            "/api/v2/projects?limit=1": {"projects": [{"id": "flat-cell", "org_id": "org-a"}]},
            "/api/v2/projects?limit=100&search=livio": {
                "projects": [{"id": "flat-cell", "name": "livio"}]
            },
            "/api/v2/projects/flat-cell": {
                "project": {
                    "id": "flat-cell",
                    "org_id": "org-a",
                    "compute_time_seconds": 10,
                    "consumption_period_start": "2026-09-01T00:00:00Z",
                }
            },
            "/api/v2/organizations/org-a": {"plan": "free"},
        }
    )
    database = NeonDatabase(
        "org-key", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )

    assert await database.verify() == "org-a"
    assert await database.find_project("livio") == "flat-cell"
    assert len(await database.read_quotas("flat-cell")) == 1


async def test_an_organization_key_without_projects_still_connects() -> None:
    api = Api({"/api/v2/projects?limit=1": {"projects": []}})
    database = NeonDatabase(
        "org-key", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )
    assert await database.verify() == "organization"


async def test_a_refused_neon_key_is_refused_not_unavailable() -> None:
    api = Api({"/api/v2/users/me": 401})
    database = NeonDatabase(
        "bad", lambda _: None, api_url="https://neon.test/api/v2", transport=api.transport
    )
    with pytest.raises(ProviderAuthorizationError):
        await database.verify()
