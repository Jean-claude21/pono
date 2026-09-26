"""T008 to T011, T017 — the adapters of the development runtime, against the payload shapes
the real APIs publish (Coolify v4 OpenAPI, Neon v2, GitHub REST), every key use traced (D-007)."""

import base64
import json
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from pono_api.application.ports import (
    DevelopmentDatabaseError,
    FileChange,
    ForbiddenWriteError,
    GateRefusedError,
    RuntimeHostError,
    RuntimeSpec,
    RuntimeUnreachableError,
)
from pono_api.domain.runtimes import RuntimeTicket
from pono_api.infrastructure.crypto import CredentialCipher
from pono_api.infrastructure.providers.coolify import CoolifyHosting
from pono_api.infrastructure.providers.neon import NeonDatabase
from pono_api.infrastructure.runtime.gate import HttpRuntimeGate
from tests.github_stub import GitHubStub
from tests.unit.test_providers import recorder

pytestmark = pytest.mark.unit

REPO = "/repos/alice/fluxio"
HEAD, NEXT = "a" * 40, "b" * 40


class Scripted:
    """A method-aware API double that records what it received."""

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], Callable[[httpx.Request], httpx.Response]] = {}
        self.calls: list[tuple[str, str, object]] = []

    def on(self, method: str, path: str, body: object = None, status: int = 200) -> None:
        self.routes[(method, path)] = lambda _: httpx.Response(
            status, content=json.dumps(body).encode() if body is not None else b""
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode()
        payload = json.loads(request.content) if request.content else None
        self.calls.append((request.method, path, payload))
        route = self.routes.get((request.method, path))
        return route(request) if route else httpx.Response(404, json={"message": "not found"})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def sent(self, method: str, path: str) -> list[object]:
        return [body for m, p, body in self.calls if (m, p) == (method, path)]


# --- code host ---------------------------------------------------------------------------------


def _code_host(stub: GitHubStub, default_branch: str = "main") -> None:
    stub.on("GET", REPO, body={"default_branch": default_branch})
    stub.on("GET", f"{REPO}/git/ref/heads/dev", body={"object": {"sha": HEAD}})
    stub.on("POST", f"{REPO}/git/blobs", 201, {"sha": "blob-1"})
    stub.on("POST", f"{REPO}/git/trees", 201, {"sha": "tree-1"})
    stub.on("POST", f"{REPO}/git/commits", 201, {"sha": NEXT})
    stub.on("PATCH", f"{REPO}/git/refs/heads/dev", body={"object": {"sha": NEXT}})


async def test_a_batch_becomes_one_commit_on_the_development_branch_never_forced() -> None:
    stub = GitHubStub()
    _code_host(stub)
    stub.on("GET", f"{REPO}/contents/old.ts?ref={HEAD}", body={"sha": "x"})

    written = await stub.adapter().commit_to_development(
        "inst-1",
        "alice/fluxio",
        branch="dev",
        expected_head=HEAD,
        changes=[FileChange("src/a.ts", b"export const a = 1;"), FileChange("old.ts", None)],
        message="pono: save 2 files",
    )

    assert (written.commit_sha, written.head, written.conflicts) == (NEXT, NEXT, ())
    bodies = {r.url.path: json.loads(r.content) for r in stub.writes()}
    assert bodies[f"{REPO}/git/blobs"] == {
        "content": base64.b64encode(b"export const a = 1;").decode(),
        "encoding": "base64",
    }
    assert bodies[f"{REPO}/git/trees"]["tree"] == [
        {"path": "src/a.ts", "mode": "100644", "type": "blob", "sha": "blob-1"},
        {"path": "old.ts", "mode": "100644", "type": "blob", "sha": None},
    ]
    assert bodies[f"{REPO}/git/commits"]["parents"] == [HEAD]
    assert bodies[f"{REPO}/git/refs/heads/dev"] == {"sha": NEXT, "force": False}


async def test_files_the_branch_changed_meanwhile_are_left_out_as_conflicts() -> None:
    stub = GitHubStub()
    _code_host(stub)
    stub.on(
        "GET",
        f"{REPO}/compare/{'c' * 40}...{HEAD}",
        body={"files": [{"filename": "src/a.ts"}, {"filename": "README.md"}]},
    )

    written = await stub.adapter().commit_to_development(
        "inst-1",
        "alice/fluxio",
        branch="dev",
        expected_head="c" * 40,
        changes=[FileChange("src/a.ts", b"mine"), FileChange("src/b.ts", b"new")],
        message="pono: save",
    )

    assert written.conflicts == ("src/a.ts",)
    tree = next(r for r in stub.writes() if r.url.path.endswith("/git/trees"))
    assert [e["path"] for e in json.loads(tree.content)["tree"]] == ["src/b.ts"]


async def test_only_conflicts_means_no_commit_at_all() -> None:
    stub = GitHubStub()
    _code_host(stub)
    stub.on("GET", f"{REPO}/compare/{'c' * 40}...{HEAD}", body={"files": [{"filename": "a.ts"}]})

    written = await stub.adapter().commit_to_development(
        "inst-1",
        "alice/fluxio",
        branch="dev",
        expected_head="c" * 40,
        changes=[FileChange("a.ts", b"x")],
        message="m",
    )

    assert (written.commit_sha, written.head, written.conflicts) == (None, HEAD, ("a.ts",))
    assert stub.writes() == []


@pytest.mark.parametrize("branch", ["main", "pono/runtime", ""])
async def test_the_default_or_a_proposal_branch_never_receives_a_runtime_write(
    branch: str,
) -> None:
    stub = GitHubStub()
    _code_host(stub)

    with pytest.raises(ForbiddenWriteError):
        await stub.adapter().commit_to_development(
            "inst-1",
            "alice/fluxio",
            branch=branch,
            expected_head=None,
            changes=[FileChange("a.ts", b"x")],
            message="m",
        )
    assert stub.writes() == []


async def test_runtime_files_are_proposed_in_one_commit_and_one_pull_request() -> None:
    stub = GitHubStub()
    _code_host(stub)
    stub.on("POST", f"{REPO}/git/refs", 201, {"ref": "refs/heads/pono/runtime"})
    stub.on("POST", f"{REPO}/pulls", 201, {"html_url": "https://github.com/alice/fluxio/pull/9"})

    url = await stub.adapter().propose_files(
        "inst-1",
        "alice/fluxio",
        base="dev",
        branch="pono/runtime",
        files={".pono/runtime/gate.mjs": "// gate", ".pono/runtime/Dockerfile": "FROM node"},
        title="Add the Pono development runtime",
        body="…",
    )

    assert url == "https://github.com/alice/fluxio/pull/9"
    bodies = {r.url.path: json.loads(r.content) for r in stub.writes()}
    assert [e["path"] for e in bodies[f"{REPO}/git/trees"]["tree"]] == [
        ".pono/runtime/Dockerfile",
        ".pono/runtime/gate.mjs",
    ]
    assert bodies[f"{REPO}/pulls"]["base"] == "dev"
    with pytest.raises(ForbiddenWriteError):
        await stub.adapter().propose_files(
            "inst-1", "alice/fluxio", base="dev", branch="dev", files={}, title="", body=""
        )


async def test_the_deploy_key_is_read_only_and_can_be_removed() -> None:
    stub = GitHubStub()
    stub.on("POST", f"{REPO}/keys", 201, {"id": 77})
    stub.on("DELETE", f"{REPO}/keys/77", 204)

    reference = await stub.adapter().add_deploy_key(
        "inst-1", "alice/fluxio", title="pono-runtime", public_key="ssh-ed25519 AAAA"
    )
    await stub.adapter().remove_deploy_key("inst-1", "alice/fluxio", reference)

    assert reference == "77"
    assert json.loads(stub.writes()[0].content)["read_only"] is True
    assert stub.adapter().clone_url("alice/fluxio") == "git@github.com:alice/fluxio.git"


# --- database ----------------------------------------------------------------------------------


def _neon(api: Scripted, *, default: bool = False, shared_host: bool = False) -> NeonDatabase:
    api.on(
        "GET",
        "/api/v2/projects/p1/branches",
        {
            "branches": [
                {"id": "br-dev", "name": "dev", "default": default},
                {"id": "br-main", "name": "main", "default": not default},
            ]
        },
    )
    api.on(
        "GET",
        "/api/v2/projects/p1/endpoints",
        {
            "endpoints": [
                {"branch_id": "br-dev", "type": "read_write", "host": "ep-dev.neon.tech"},
                {
                    "branch_id": "br-main",
                    "type": "read_write",
                    "host": "ep-dev.neon.tech" if shared_host else "ep-main.neon.tech",
                },
            ]
        },
    )
    api.on(
        "GET",
        "/api/v2/projects/p1/branches/br-dev/databases",
        {"databases": [{"name": "neondb", "owner_name": "neondb_owner"}]},
    )
    api.on(
        "GET",
        "/api/v2/projects/p1/connection_uri?branch_id=br-dev&database_name=neondb"
        "&role_name=neondb_owner",
        {"uri": "postgresql://neondb_owner:pw@ep-dev.neon.tech/neondb"},
    )
    return NeonDatabase(
        "key", recorder()[1], api_url="https://neon.test/api/v2", transport=api.transport
    )  # type: ignore[arg-type]


@pytest.mark.parametrize(("development", "production"), [("br-dev", "br-main"), ("dev", "main")])
async def test_the_runtime_gets_the_development_branch_and_both_hosts(
    development: str, production: str
) -> None:
    target = await _neon(Scripted()).development_target("p1", development, production)

    assert (target.host, target.production_host) == ("ep-dev.neon.tech", "ep-main.neon.tech")
    assert target.url.startswith("postgresql://")


@pytest.mark.parametrize(
    ("development", "production", "options", "code"),
    [
        ("br-main", "br-main", {}, "runtime.production_database"),
        ("br-dev", "br-main", {"default": True}, "runtime.production_database"),
        ("br-dev", "br-main", {"shared_host": True}, "runtime.production_database"),
        ("br-gone", "br-main", {}, "runtime.database_missing"),
    ],
)
async def test_the_production_database_is_never_a_runtime_s(
    development: str, production: str, options: dict[str, bool], code: str
) -> None:
    with pytest.raises(DevelopmentDatabaseError) as refused:
        await _neon(Scripted(), **options).development_target("p1", development, production)
    assert refused.value.code == code


# --- runtime host ------------------------------------------------------------------------------

SPEC = RuntimeSpec(
    name="Fluxio Runtime",
    clone_url="git@github.com:alice/fluxio.git",
    branch="dev",
    private_key="-----BEGIN OPENSSH PRIVATE KEY-----",
    variables={"PONO_RUNTIME_ID": "r1", "DATABASE_URL": "postgresql://dev"},
    memory="1g",
)


def _coolify(api: Scripted, servers: list[dict[str, object]]) -> CoolifyHosting:
    api.on("GET", "/api/v1/servers", servers)
    api.on("GET", "/api/v1/projects", [{"name": "Other", "uuid": "p0"}])
    api.on("POST", "/api/v1/projects", {"uuid": "p9"})
    api.on("POST", "/api/v1/security/keys", {"uuid": "k1"})
    api.on("POST", "/api/v1/applications/private-deploy-key", {"uuid": "app-1"})
    api.on("POST", "/api/v1/applications/app-1/envs", {"uuid": "env"})
    return CoolifyHosting("https://coolify.test", "token", recorder()[1], transport=api.transport)  # type: ignore[arg-type]


async def test_the_runtime_is_created_in_its_own_project_with_a_memory_limit() -> None:
    api = Scripted()
    host = _coolify(api, [{"uuid": "s1", "ip": "13.140.178.49", "settings": {}}])

    handle = await host.create_runtime(SPEC)

    assert (handle.ref, handle.key_ref) == ("app-1", "k1")
    assert handle.url.startswith("https://fluxio-runtime-dev-")
    assert handle.url.endswith(".13.140.178.49.sslip.io")
    (created,) = api.sent("POST", "/api/v1/applications/private-deploy-key")
    assert isinstance(created, dict)
    assert created["project_uuid"] == "p9"
    assert created["git_branch"] == "dev"
    assert created["limits_memory"] == "1g"
    assert created["is_auto_deploy_enabled"] is False
    assert created["dockerfile_location"] == "/.pono/runtime/Dockerfile"
    assert {body["key"] for body in api.sent("POST", "/api/v1/applications/app-1/envs")} == {  # type: ignore[index]
        "PONO_RUNTIME_ID",
        "DATABASE_URL",
    }


async def test_a_wildcard_domain_is_preferred_and_two_servers_are_ambiguous() -> None:
    api = Scripted()
    host = _coolify(
        api, [{"uuid": "s1", "ip": "1.2.3.4", "settings": {"wildcard_domain": "https://apps.test"}}]
    )
    assert (await host.create_runtime(SPEC)).url.endswith(".apps.test")

    two = _coolify(Scripted(), [{"uuid": "s1"}, {"uuid": "s2"}])
    with pytest.raises(RuntimeHostError) as refused:
        await two.create_runtime(SPEC)
    assert refused.value.code == "runtime.server_ambiguous"


@pytest.mark.parametrize(
    ("status", "deployment", "expected"),
    [
        ("running:healthy", None, "running"),
        ("exited:unhealthy", "in_progress", "starting"),
        ("exited:unhealthy", "failed", "failed"),
        ("exited:unhealthy", "finished", "stopped"),
    ],
)
async def test_the_runtime_status_reads_the_host(
    status: str, deployment: str | None, expected: str
) -> None:
    api = Scripted()
    api.on("GET", "/api/v1/applications/app-1", {"uuid": "app-1", "status": status})
    api.on(
        "GET",
        "/api/v1/deployments/applications/app-1?skip=0&take=1",
        {"deployments": [{"status": deployment}] if deployment else []},
    )
    host = CoolifyHosting("https://coolify.test", "t", recorder()[1], transport=api.transport)  # type: ignore[arg-type]

    assert await host.runtime_status("app-1") == expected


# --- gate client -------------------------------------------------------------------------------


def _gate(api: Scripted) -> tuple[HttpRuntimeGate, bytes]:
    gate = HttpRuntimeGate(
        CredentialCipher(CredentialCipher.generate_key()), transport=api.transport
    )
    return gate, gate.new_credentials().sealed_token


async def test_the_gate_client_carries_the_token_and_reads_the_status() -> None:
    api = Scripted()
    api.on(
        "GET",
        "/__pono/status",
        {
            "awake": True,
            "lastActivityAt": "2026-09-26T12:00:00Z",
            "head": HEAD,
            "conflicts": ["src/a.ts"],
            "errors": [{"source": "compile", "message": "boom"}],
            "databaseHost": "ep-dev.neon.tech",
        },
    )
    api.on("PUT", "/__pono/files", status=204)
    gate, sealed = _gate(api)

    status = await gate.status("https://rt.test", sealed)
    await gate.write("https://rt.test", sealed, "src/a.ts", b"x")
    await gate.write("https://rt.test", sealed, "src/b.ts", None)

    assert (status.awake, status.head, status.conflicts) == (True, HEAD, ("src/a.ts",))
    assert status.database_host == "ep-dev.neon.tech"
    assert api.sent("PUT", "/__pono/files") == [
        {"path": "src/a.ts", "content": base64.b64encode(b"x").decode()},
        {"path": "src/b.ts", "delete": True},
    ]


async def test_the_gate_client_says_refused_and_unreachable_apart() -> None:
    api = Scripted()
    api.on("PUT", "/__pono/files", {"code": "runtime.path_refused"}, status=422)
    gate, sealed = _gate(api)

    with pytest.raises(GateRefusedError):
        await gate.write("https://rt.test", sealed, "../x", b"x")
    with pytest.raises(RuntimeUnreachableError):
        await gate.status("https://rt.test", sealed)


def test_credentials_are_sealed_and_the_ticket_is_signed_with_the_same_token() -> None:
    cipher = CredentialCipher(CredentialCipher.generate_key())
    gate = HttpRuntimeGate(cipher)
    credentials = gate.new_credentials()
    runtime = UUID(int=7)

    ticket = gate.ticket(credentials.sealed_token, runtime)

    assert credentials.token.encode() not in credentials.sealed_token
    assert cipher.decrypt(credentials.sealed_token) == SecretStr(credentials.token)
    assert credentials.public_key.startswith("ssh-ed25519 ")
    assert "OPENSSH PRIVATE KEY" in credentials.private_key
    assert RuntimeTicket.check(ticket, credentials.token, runtime) is not None
