"""Shared steps for workshop tests: a signed-in person with every provider connected."""

import json
from datetime import timedelta

import httpx

from pono_api.application.identity import CodeHostUser
from pono_api.application.ports import DetectedEnvironment, HostedEnvironment, PreviewRecord
from pono_api.domain.projects import DeploymentStatus, EnvironmentKind, ResourceStatus
from tests.conftest import FakeIdentity, sign_in_as
from tests.fakes import NOW, World, deployment

ALICE = CodeHostUser("1001", "alice", "alice@example.test")
BOB = CodeHostUser("2002", "bob", "bob@example.test")

LECTIO = "alice/lectio-reads"
NETTIO = "alice/nettio"
LECTIO_FLUXIO = json.dumps(
    {
        "fluxioVersion": 1,
        "slug": "lectio-reads",
        "github": {"repo": LECTIO, "defaultBranch": "main", "devBranch": "dev"},
        "neon": {"projectId": "royal-mouse", "branches": {"main": "br-1", "dev": "br-2"}},
        "netlify": {"siteId": "site-lectio", "url": "https://lectio-reads.netlify.app"},
        "coolify": {"applicationUuid": "app-lectio-dev", "devUrl": "https://lectio-dev.test"},
    }
)


async def connect_everything(client: httpx.AsyncClient, identity: FakeIdentity) -> None:
    await sign_in_as(client, identity, ALICE)
    assert (await client.post("/api/v1/connections/code-host")).status_code == 201
    for body in (
        {"kind": "hosting", "provider": "netlify", "authorization": "netlify-key"},
        {
            "kind": "hosting",
            "provider": "coolify",
            "authorization": "coolify-key",
            "endpoint": "https://app.coolify.test",
        },
        {"kind": "database", "provider": "neon", "authorization": "neon-key"},
    ):
        response = await client.post("/api/v1/connections", json=body)
        assert response.status_code == 201, response.text


def stage_lectio(world: World) -> None:
    """lectio-reads as found in reality: Fluxio manifest, Netlify production, Coolify dev."""

    world.code_host.files[(LECTIO, ".fluxio/project.json")] = LECTIO_FLUXIO
    world.factory.hosting_adapters["netlify"].environments["site-lectio"] = HostedEnvironment(
        status=ResourceStatus.FOUND,
        url="https://lectio-reads.netlify.app",
        deployments=(deployment("netlify-2", author="Jean-claude21"), deployment("netlify-1")),
        previews=(
            PreviewRecord(
                external_ref="1",
                url="https://deploy-preview-1--lectio-reads.netlify.app",
                opened_at=NOW - timedelta(days=1),
                branch="dev",
                review_url=f"https://code.test/{LECTIO}/pull/1",
            ),
            PreviewRecord(
                external_ref="2",
                url="https://deploy-preview-2--lectio-reads.netlify.app",
                opened_at=NOW - timedelta(hours=5),
                branch="feature",
                review_url=f"https://code.test/{LECTIO}/pull/2",
            ),
        ),
    )
    world.factory.hosting_adapters["coolify"].environments["app-lectio-dev"] = HostedEnvironment(
        status=ResourceStatus.FOUND,
        url="https://lectio-dev.test",
        deployments=(
            deployment("coolify-1", DeploymentStatus.SUCCEEDED, age=timedelta(days=2), author=None),
        ),
    )
    world.factory.database_adapters["neon"].projects["lectio-reads"] = "royal-mouse"


def stage_nettio(world: World) -> None:
    """nettio as found in reality: a studio project.yaml, two Coolify apps on `dev`."""

    world.code_host.files[(NETTIO, "project.yaml")] = "name: nettio\nsurfaces: [web]\n"
    coolify = world.factory.hosting_adapters["coolify"]
    coolify.detected[NETTIO] = [
        DetectedEnvironment(EnvironmentKind.DEVELOPMENT, "app-nettio", "https://nettio.test", "dev")
    ]
    coolify.environments["app-nettio"] = HostedEnvironment(
        status=ResourceStatus.FOUND, url="https://nettio.test", deployments=(deployment("n-1"),)
    )


__all__ = [
    "ALICE",
    "BOB",
    "LECTIO",
    "NETTIO",
    "connect_everything",
    "stage_lectio",
    "stage_nettio",
]
