"""US1 — import a project and see its real state, end to end against a real database.

Providers are scripted in memory; the database, row-level security and routes are real.
"""

import json
from datetime import timedelta

import httpx
import pytest

from pono_api.application.ports import HostedEnvironment
from pono_api.domain.projects import DeploymentStatus, ResourceStatus
from tests.conftest import FakeIdentity, owner_fetch, requires_database, sign_in_as
from tests.fakes import World, deployment
from tests.integration.workshop_setup import (
    ALICE,
    LECTIO,
    NETTIO,
    connect_everything,
    stage_lectio,
    stage_nettio,
)

pytestmark = [pytest.mark.integration, requires_database]


async def test_lectio_imports_with_its_real_environments_and_a_proposed_manifest(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)

    response = await client.post("/api/v1/projects", json={"repository": LECTIO})

    assert response.status_code == 201, response.text
    project = response.json()
    assert project["name"] == "lectio-reads"
    assert project["manifestStatus"] == "proposed"
    assert project["manifestProposalUrl"] == f"https://code.test/{LECTIO}/pull/1"
    assert project["state"] == "active"  # last commit two hours ago
    assert project["stateReason"] == "recent_activity"
    assert project["stale"] is False
    assert project["refreshedAt"] is not None
    assert project["databaseStatus"] == "found"

    kinds = [(e["kind"], e["url"], e["linkStatus"]) for e in project["environments"]]
    assert kinds == [
        ("production", "https://lectio-reads.netlify.app", "up"),
        ("development", "https://lectio-dev.test", "up"),
        ("preview", "https://deploy-preview-2--lectio-reads.netlify.app", "up"),
    ]
    assert len(project["previews"]) == 2
    # The most recent deployment of any standing environment, with who made it.
    last = project["lastDeployment"]
    assert (last["environmentKind"], last["status"], last["author"]) == (
        "development",
        "succeeded",
        "alice",
    )

    # The pre-filled manifest was proposed on its own branch, with the Fluxio identifiers.
    ((repository, branch, path, content),) = world.code_host.proposals
    assert (repository, branch, path) == (LECTIO, "pono/manifest", ".pono/project.json")
    manifest = json.loads(content)
    assert manifest["importedFrom"] == "fluxio"
    assert manifest["database"] == {
        "provider": "neon",
        "ref": "royal-mouse",
        "branches": {"production": "main", "development": "dev"},
    }


async def test_a_host_that_does_not_say_who_deployed_gets_the_commit_author(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    await client.post("/api/v1/projects", json={"repository": LECTIO})

    authors = await owner_fetch(
        "SELECT d.author FROM deployments d JOIN environments e ON e.id = d.environment_id "
        "WHERE e.kind = 'development'"
    )
    assert [row["author"] for row in authors] == ["alice"]


async def test_every_use_of_a_provider_key_is_traced_without_the_key(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    await client.post("/api/v1/projects", json={"repository": LECTIO})

    events = await owner_fetch(
        "SELECT c.provider, e.action FROM connection_events e "
        "JOIN connections c ON c.id = e.connection_id"
    )
    actions = {(row["provider"], row["action"]) for row in events}
    assert {
        ("netlify", "verify"),
        ("netlify", "read_environment"),
        ("coolify", "read_environment"),
        ("neon", "read_project"),
    } <= actions
    stored = await owner_fetch("SELECT secret_ciphertext FROM connections WHERE kind = 'hosting'")
    assert all(b"netlify-key" not in bytes(row["secret_ciphertext"]) for row in stored)


async def test_nettio_imports_from_its_project_yaml_and_what_the_host_links(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_nettio(world)

    project = (await client.post("/api/v1/projects", json={"repository": NETTIO})).json()

    assert [(e["kind"], e["provider"]) for e in project["environments"]] == [
        ("development", "coolify")
    ]
    manifest = json.loads(world.code_host.proposals[0][3])
    assert manifest["importedFrom"] == "studio-project-yaml"
    assert "database" not in manifest


async def test_a_repository_with_a_pono_manifest_is_read_and_nothing_is_proposed(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    world.code_host.files[(NETTIO, ".pono/project.json")] = json.dumps(
        {
            "schemaVersion": 1,
            "name": "nettio",
            "environments": [{"kind": "production", "url": "https://nettio.example.test"}],
        }
    )

    project = (await client.post("/api/v1/projects", json={"repository": NETTIO})).json()

    assert project["manifestStatus"] == "present"
    assert project["manifestProposalUrl"] is None
    assert world.code_host.proposals == []
    (production,) = project["environments"]
    assert (production["url"], production["resourceStatus"]) == (
        "https://nettio.example.test",
        "unknown",
    )


async def test_a_repository_is_imported_once_per_organization(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_nettio(world)
    await client.post("/api/v1/projects", json={"repository": NETTIO})

    again = await client.post("/api/v1/projects", json={"repository": "ALICE/Nettio"})

    assert again.status_code == 409
    assert again.json() == {"error": {"code": "project.already_imported"}}
    repositories = (await client.get("/api/v1/repositories")).json()
    assert {r["fullName"]: r["alreadyImported"] for r in repositories} == {
        LECTIO: False,
        NETTIO: True,
    }


@pytest.mark.parametrize(
    ("repository", "status", "code"),
    [
        ("alice/secret", 422, "project.repository_unreachable"),
        ("not a repository", 422, "request.invalid"),
    ],
)
async def test_unreachable_or_malformed_repositories_are_refused(
    clean_database: None,
    client: httpx.AsyncClient,
    identity: FakeIdentity,
    repository: str,
    status: int,
    code: str,
) -> None:
    await connect_everything(client, identity)
    response = await client.post("/api/v1/projects", json={"repository": repository})
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)


async def test_without_a_code_host_nothing_can_be_listed_or_imported(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)
    for response in (
        await client.get("/api/v1/repositories"),
        await client.post("/api/v1/projects", json={"repository": LECTIO}),
    ):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "connection.code_host_missing"


async def test_an_unavailable_host_keeps_the_last_state_and_marks_it_stale(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    first = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()

    world.factory.hosting_adapters["netlify"].unavailable = True
    assert (await client.post(f"/api/v1/projects/{first['id']}/refresh")).status_code == 202

    after = (await client.get(f"/api/v1/projects/{first['id']}")).json()
    assert after["stale"] is True
    assert after["refreshedAt"] == first["refreshedAt"]
    assert after["state"] == first["state"]
    assert after["environments"][0]["url"] == "https://lectio-reads.netlify.app"


async def test_a_production_that_does_not_answer_makes_the_project_failing(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    stage_nettio(world)
    world.links.down.add("https://lectio-reads.netlify.app")
    lectio = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()
    await client.post("/api/v1/projects", json={"repository": NETTIO})

    workshop = (await client.get("/api/v1/projects")).json()

    assert lectio["state"] == "failing"
    assert lectio["environments"][0]["linkStatus"] == "down"
    assert workshop["counts"] == {
        "healthy": 0,
        "active": 1,
        "warning": 0,
        "failing": 1,
        "idle": 0,
    }
    assert workshop["verdicts"][0] == {"projectId": lectio["id"], "code": "project.production_down"}
    assert {"projectId": lectio["id"], "code": "project.manifest_proposed"} in workshop["verdicts"]
    failing = (await client.get("/api/v1/projects", params={"state": "failing"})).json()
    assert [p["id"] for p in failing["projects"]] == [lectio["id"]]
    assert "previews" not in failing["projects"][0]


async def test_a_failed_production_deployment_makes_the_project_failing(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    world.factory.hosting_adapters["netlify"].environments["site-lectio"] = HostedEnvironment(
        status=ResourceStatus.FOUND,
        url="https://lectio-reads.netlify.app",
        deployments=(deployment("broken", DeploymentStatus.FAILED, age=timedelta(minutes=5)),),
    )

    project = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()

    assert (project["state"], project["stateReason"]) == ("failing", "deployment_failed")


async def test_merged_proposal_makes_the_manifest_the_truth_and_closed_is_never_reproposed(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    stage_nettio(world)
    lectio = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()
    nettio = (await client.post("/api/v1/projects", json={"repository": NETTIO})).json()

    world.code_host.proposal_states[lectio["manifestProposalUrl"]] = "merged"
    world.code_host.files[(LECTIO, ".pono/project.json")] = json.dumps(
        {
            "schemaVersion": 1,
            "name": "lectio",
            "environments": [
                {
                    "kind": "production",
                    "url": "https://lectio-reads.netlify.app",
                    "hosting": {"provider": "netlify", "ref": "site-lectio"},
                }
            ],
        }
    )
    world.code_host.proposal_states[nettio["manifestProposalUrl"]] = "closed"
    for project in (lectio, nettio):
        await client.post(f"/api/v1/projects/{project['id']}/refresh")

    merged = (await client.get(f"/api/v1/projects/{lectio['id']}")).json()
    closed = (await client.get(f"/api/v1/projects/{nettio['id']}")).json()
    assert (merged["manifestStatus"], merged["name"]) == ("present", "lectio")
    assert [e["kind"] for e in merged["environments"]] == ["production", "preview"]
    assert closed["manifestStatus"] == "absent"
    assert len(world.code_host.proposals) == 2


async def test_a_closed_change_request_hides_its_preview(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    world.code_host.proposal_states[f"https://code.test/{LECTIO}/pull/2"] = "closed"

    project = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()

    assert [p["url"] for p in project["previews"]] == [
        "https://deploy-preview-1--lectio-reads.netlify.app"
    ]


async def test_an_expired_host_key_puts_the_project_in_warning(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity, world: World
) -> None:
    await connect_everything(client, identity)
    stage_lectio(world)
    project = (await client.post("/api/v1/projects", json={"repository": LECTIO})).json()

    world.factory.hosting_adapters["coolify"].refuse = True
    await client.post(f"/api/v1/projects/{project['id']}/refresh")

    after = (await client.get(f"/api/v1/projects/{project['id']}")).json()
    assert (after["state"], after["stateReason"]) == ("warning", "connection_expired")
    connections = (await client.get("/api/v1/connections")).json()
    assert {c["provider"]: c["status"] for c in connections}["coolify"] == "expired"
    workshop = (await client.get("/api/v1/projects")).json()
    assert {"projectId": project["id"], "code": "connection.expired"} in workshop["verdicts"]


async def test_refresh_and_detail_of_an_unknown_project_are_not_found(
    clean_database: None, client: httpx.AsyncClient, identity: FakeIdentity
) -> None:
    await sign_in_as(client, identity, ALICE)
    unknown = "01980000-0000-7000-8000-000000000000"
    for response in (
        await client.get(f"/api/v1/projects/{unknown}"),
        await client.post(f"/api/v1/projects/{unknown}/refresh"),
    ):
        assert response.status_code == 404
        assert response.json() == {"error": {"code": "project.not_found"}}
