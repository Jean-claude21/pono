"""In-memory providers for tests: no network, fully scripted, recording what they are asked."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pono_api.application.ports import (
    ChangedFile,
    ChangeRequest,
    ChatRecipient,
    ChatStart,
    CheckState,
    DatabaseSnapshot,
    DeploymentRecord,
    DetectedEnvironment,
    DevelopmentCommit,
    DevelopmentDatabase,
    DevelopmentDatabaseError,
    FileChange,
    ForbiddenWriteError,
    GateRefusedError,
    GateStatus,
    HostedEnvironment,
    HostRuntimeStatus,
    KeyUse,
    PreviewState,
    ProposalState,
    ProtectionRefusedError,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RaisedAlert,
    Recipient,
    RepositoryInfo,
    RollbackUnsupportedError,
    RuntimeCredentials,
    RuntimeHandle,
    RuntimeHostError,
    RuntimeSpec,
    RuntimeUnreachableError,
    StoredConnection,
)
from pono_api.application.refresh_project import Providers
from pono_api.domain.projects import (
    ConnectionKind,
    DeploymentStatus,
    EnvironmentKind,
    LinkStatus,
    ResourceStatus,
)
from pono_api.domain.quotas import QuotaReading
from pono_api.domain.releases import ProtectionStatus
from pono_api.infrastructure.manifests import RepositoryManifests

NOW = datetime.now(UTC)


@dataclass
class FakeCodeHost:
    provider: str = "github"
    account_installations: dict[str, str] = field(default_factory=lambda: {"1001": "inst-1"})
    repositories: list[RepositoryInfo] = field(
        default_factory=lambda: [
            RepositoryInfo("alice/lectio-reads", "main"),
            RepositoryInfo("alice/nettio", "main"),
        ]
    )
    files: dict[tuple[str, str], str] = field(default_factory=dict)
    last_commit: datetime | None = NOW - timedelta(hours=2)
    proposals: list[tuple[str, str, str, str]] = field(default_factory=list)
    proposal_states: dict[str, ProposalState] = field(default_factory=dict)
    revoked: list[str] = field(default_factory=list)
    active: bool = True
    unavailable: bool = False
    authors: dict[str, str] = field(default_factory=lambda: {"abc123": "alice"})
    # Guarded release (002): open changes per repository, their files, the checks Pono publishes.
    changes: dict[str, list[ChangeRequest]] = field(default_factory=dict)
    finished: dict[tuple[str, int], ChangeRequest] = field(default_factory=dict)
    change_file_sets: dict[tuple[str, int], list[ChangedFile]] = field(default_factory=dict)
    checks: list[tuple[str, str, CheckState]] = field(default_factory=list)
    protection: dict[str, ProtectionStatus] = field(default_factory=dict)
    protection_refusal: str | None = None
    protected: list[tuple[str, str]] = field(default_factory=list)
    checks_unavailable: bool = False
    # Development runtime (004): proposals of several files, heads, commits, deploy keys.
    file_proposals: list[tuple[str, str, str, dict[str, str]]] = field(default_factory=list)
    heads: dict[tuple[str, str], str] = field(default_factory=dict)
    moved_paths: set[str] = field(default_factory=set)
    development_commits: list[tuple[str, str, str | None, list[FileChange], str]] = field(
        default_factory=list
    )
    deploy_keys: dict[str, tuple[str, str]] = field(default_factory=dict)

    def _answer(self) -> None:
        if self.unavailable:
            raise ProviderUnavailableError("code host down")

    async def find_installation(self, account_id: str) -> str | None:
        self._answer()
        return self.account_installations.get(account_id)

    async def installation_active(self, installation_id: str) -> bool:
        self._answer()
        return self.active

    async def revoke_installation(self, installation_id: str) -> None:
        self._answer()
        self.revoked.append(installation_id)

    async def list_repositories(self, installation_id: str) -> list[RepositoryInfo]:
        self._answer()
        return list(self.repositories)

    async def read_file(
        self, installation_id: str, repository: str, path: str, ref: str | None = None
    ) -> str | None:
        self._answer()
        return self.files.get((repository, path))

    async def last_commit_at(self, installation_id: str, repository: str) -> datetime | None:
        self._answer()
        return self.last_commit

    async def commit_author(
        self, installation_id: str, repository: str, commit_sha: str
    ) -> str | None:
        self._answer()
        return self.authors.get(commit_sha)

    async def propose_file(
        self,
        installation_id: str,
        repository: str,
        *,
        base: str,
        branch: str,
        path: str,
        content: str,
        title: str,
        body: str,
    ) -> str:
        self._answer()
        self.proposals.append((repository, branch, path, content))
        return f"https://code.test/{repository}/pull/{len(self.proposals)}"

    async def proposal_state(self, installation_id: str, proposal_url: str) -> ProposalState:
        self._answer()
        return self.proposal_states.get(proposal_url, "open")

    async def list_changes(
        self, installation_id: str, repository: str, base_branch: str
    ) -> list[ChangeRequest]:
        self._answer()
        return [c for c in self.changes.get(repository, []) if c.base_branch == base_branch]

    async def read_change(
        self, installation_id: str, repository: str, number: int
    ) -> ChangeRequest:
        self._answer()
        return self.finished[(repository, number)]

    async def change_files(
        self, installation_id: str, repository: str, number: int
    ) -> list[ChangedFile]:
        self._answer()
        return list(self.change_file_sets.get((repository, number), []))

    async def set_release_check(
        self,
        installation_id: str,
        repository: str,
        head_sha: str,
        state: CheckState,
        *,
        summary: str,
        details_url: str | None,
    ) -> None:
        self._answer()
        if self.checks_unavailable:
            raise ProviderUnavailableError("checks down")
        self.checks.append((repository, head_sha, state))

    async def read_protection(
        self, installation_id: str, repository: str, branch: str
    ) -> ProtectionStatus:
        self._answer()
        return self.protection.get(repository, ProtectionStatus.UNPROTECTED)

    async def apply_protection(self, installation_id: str, repository: str, branch: str) -> None:
        self._answer()
        if self.protection_refusal:
            raise ProtectionRefusedError(self.protection_refusal)
        self.protected.append((repository, branch))
        self.protection[repository] = ProtectionStatus.PROTECTED

    async def propose_files(
        self,
        installation_id: str,
        repository: str,
        *,
        base: str,
        branch: str,
        files: dict[str, str],
        title: str,
        body: str,
    ) -> str:
        self._answer()
        self.file_proposals.append((repository, base, branch, dict(files)))
        return f"https://code.test/{repository}/pull/{100 + len(self.file_proposals)}"

    async def branch_head(self, installation_id: str, repository: str, branch: str) -> str:
        self._answer()
        return self.heads.get((repository, branch), "head-0")

    def clone_url(self, repository: str) -> str:
        return f"git@code.test:{repository}.git"

    async def commit_to_development(
        self,
        installation_id: str,
        repository: str,
        *,
        branch: str,
        expected_head: str | None,
        changes: list[FileChange],
        message: str,
    ) -> DevelopmentCommit:
        self._answer()
        default = next(
            (r.default_branch for r in self.repositories if r.full_name == repository), ""
        )
        if branch == default or branch.startswith("pono/"):
            raise ForbiddenWriteError(branch)
        head = self.heads.get((repository, branch), "head-0")
        moved = self.moved_paths if expected_head != head else set()
        conflicts = tuple(sorted({c.path for c in changes} & moved))
        kept = [c for c in changes if c.path not in conflicts]
        if not kept:
            return DevelopmentCommit(None, head, conflicts)
        self.development_commits.append((repository, branch, expected_head, kept, message))
        commit = f"commit-{len(self.development_commits)}"
        self.heads[(repository, branch)] = commit
        return DevelopmentCommit(commit, commit, conflicts)

    async def add_deploy_key(
        self, installation_id: str, repository: str, *, title: str, public_key: str
    ) -> str:
        self._answer()
        reference = str(len(self.deploy_keys) + 1)
        self.deploy_keys[reference] = (repository, public_key)
        return reference

    async def remove_deploy_key(self, installation_id: str, repository: str, key_ref: str) -> None:
        self._answer()
        self.deploy_keys.pop(key_ref, None)

    def check_of(self, head_sha: str) -> CheckState | None:
        """The last state Pono published for a commit, as the code host would show it."""
        states = [state for _, sha, state in self.checks if sha == head_sha]
        return states[-1] if states else None


@dataclass
class FakeHosting:
    account: str
    detected: dict[str, list[DetectedEnvironment]] = field(default_factory=dict)
    environments: dict[str, HostedEnvironment] = field(default_factory=dict)
    refuse: bool = False
    unavailable: bool = False
    quotas: list[QuotaReading] = field(default_factory=list)
    previews: dict[tuple[int, str], PreviewState] = field(default_factory=dict)
    rolled_back: list[tuple[str, str]] = field(default_factory=list)
    rollback_unsupported: bool = False

    def _answer(self) -> None:
        if self.refuse:
            raise ProviderAuthorizationError("refused")
        if self.unavailable:
            raise ProviderUnavailableError("down")

    async def find_preview(self, ref: str, change_number: int, head_sha: str) -> PreviewState:
        self._answer()
        return self.previews.get((change_number, head_sha), PreviewState("absent"))

    async def rollback(self, ref: str, target: DeploymentRecord) -> str:
        self._answer()
        if self.rollback_unsupported:
            raise RollbackUnsupportedError("image pruned")
        self.rolled_back.append((ref, target.external_ref))
        return f"rollback-{target.external_ref}"

    async def verify(self) -> str:
        self._answer()
        return self.account

    async def read_quotas(self) -> list[QuotaReading]:
        self._answer()
        return list(self.quotas)

    async def detect(
        self, repository: str, name: str, default_branch: str
    ) -> list[DetectedEnvironment]:
        self._answer()
        return list(self.detected.get(repository, []))

    async def read_environment(
        self, ref: str, kind: EnvironmentKind, branch: str | None
    ) -> HostedEnvironment:
        self._answer()
        return self.environments.get(ref, HostedEnvironment(status=ResourceStatus.MISSING))


@dataclass
class FakeDatabase:
    account: str
    projects: dict[str, str] = field(default_factory=dict)
    refuse: bool = False
    quotas: dict[str, list[QuotaReading]] = field(default_factory=dict)
    branch_hosts: dict[str, str] = field(
        default_factory=lambda: {"main": "ep-main.db.test", "dev": "ep-dev.db.test"}
    )

    async def read_quotas(self, ref: str) -> list[QuotaReading]:
        return list(self.quotas.get(ref, []))

    async def verify(self) -> str:
        if self.refuse:
            raise ProviderAuthorizationError("refused")
        return self.account

    async def find_project(self, name: str) -> str | None:
        return self.projects.get(name)

    async def read_project(self, ref: str) -> DatabaseSnapshot:
        if ref in self.projects.values():
            return DatabaseSnapshot(status=ResourceStatus.FOUND, branches=("main", "dev"))
        return DatabaseSnapshot(status=ResourceStatus.MISSING)

    async def development_target(
        self, ref: str, development_branch: str, production_branch: str | None
    ) -> DevelopmentDatabase:
        if development_branch == production_branch:
            raise DevelopmentDatabaseError("runtime.production_database")
        host = self.branch_hosts.get(development_branch)
        if host is None:
            raise DevelopmentDatabaseError("runtime.database_missing")
        production = self.branch_hosts.get(production_branch or "")
        if host == production:
            raise DevelopmentDatabaseError("runtime.production_database")
        return DevelopmentDatabase(
            url=f"postgresql://owner:pw@{host}/app", host=host, production_host=production
        )


@dataclass
class FakeRuntimeHost:
    """The person's server: the runtime's application and nothing else."""

    created: list[RuntimeSpec] = field(default_factory=list)
    status: dict[str, HostRuntimeStatus] = field(default_factory=dict)
    started: list[str] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    refusal: str | None = None
    unavailable: bool = False

    def _answer(self) -> None:
        if self.unavailable:
            raise ProviderUnavailableError("host down")

    async def create_runtime(self, spec: RuntimeSpec) -> RuntimeHandle:
        self._answer()
        if self.refusal:
            raise RuntimeHostError(self.refusal)
        self.created.append(spec)
        reference = f"app-{len(self.created)}"
        self.status[reference] = "starting"
        return RuntimeHandle(reference, f"https://runtime-{len(self.created)}.test", "key-1")

    async def start_runtime(self, ref: str) -> None:
        self._answer()
        self.started.append(ref)

    async def stop_runtime(self, ref: str) -> None:
        self._answer()
        self.stopped.append(ref)
        self.status[ref] = "stopped"

    async def delete_runtime(self, ref: str, key_ref: str | None) -> None:
        self._answer()
        self.deleted.append(ref)

    async def runtime_status(self, ref: str) -> HostRuntimeStatus:
        self._answer()
        return self.status.get(ref, "missing")


@dataclass
class FakeGate:
    """The runtimes' gates: what they answer, what they were sent."""

    statuses: dict[str, GateStatus] = field(default_factory=dict)
    unreachable: set[str] = field(default_factory=set)
    refused: dict[str, str] = field(default_factory=dict)
    writes: list[tuple[str, str, bytes | None]] = field(default_factory=list)
    issued: int = 0

    def new_credentials(self) -> RuntimeCredentials:
        self.issued += 1
        return RuntimeCredentials(
            token=f"token-{self.issued}",
            sealed_token=f"sealed-{self.issued}".encode(),
            private_key="-----BEGIN OPENSSH PRIVATE KEY-----",
            public_key="ssh-ed25519 AAAA",
        )

    def ticket(self, sealed_token: bytes, runtime_id: UUID) -> str:
        return f"ticket-{runtime_id}"

    async def status(self, url: str, sealed_token: bytes) -> GateStatus:
        if url in self.unreachable:
            raise RuntimeUnreachableError(url)
        return self.statuses.get(url, awake_gate())

    async def write(self, url: str, sealed_token: bytes, path: str, content: bytes | None) -> None:
        if url in self.unreachable:
            raise RuntimeUnreachableError(url)
        if path in self.refused:
            raise GateRefusedError(self.refused[path])
        self.writes.append((url, path, content))


def awake_gate(
    *,
    database_host: str = "ep-dev.db.test",
    awake: bool = True,
    errors: tuple[dict[str, object], ...] = (),
    conflicts: tuple[str, ...] = (),
) -> GateStatus:
    return GateStatus(
        awake=awake,
        last_activity_at=NOW,
        head="head-0",
        conflicts=conflicts,
        errors=errors,
        database_host=database_host,
    )


class _Traced:
    """Wraps a fake adapter so each call reports its use, like the real keyed adapters."""

    def __init__(self, inner: object, on_use: KeyUse) -> None:
        self._inner = inner
        self._on_use = on_use

    def __getattr__(self, name: str) -> object:
        attribute = getattr(self._inner, name)
        if not callable(attribute):
            return attribute

        async def call(*args: object, **kwargs: object) -> object:
            self._on_use(name)
            return await attribute(*args, **kwargs)

        return call


@dataclass
class FakeFactory:
    hosting_adapters: dict[str, FakeHosting] = field(default_factory=dict)
    database_adapters: dict[str, FakeDatabase] = field(default_factory=dict)
    runtime_hosts: dict[str, FakeRuntimeHost] = field(
        default_factory=lambda: {"coolify": FakeRuntimeHost()}
    )

    def supports(self, kind: ConnectionKind, provider: str) -> bool:
        if kind is ConnectionKind.HOSTING:
            return provider in self.hosting_adapters
        if kind is ConnectionKind.DATABASE:
            return provider in self.database_adapters
        return False

    def seal(self, authorization: str) -> bytes:
        return b"sealed:" + authorization[::-1].encode()

    def _key(self, connection: StoredConnection) -> str:
        assert connection.secret_ciphertext is not None
        return connection.secret_ciphertext.removeprefix(b"sealed:").decode()[::-1]

    def hosting(self, connection: StoredConnection, on_use: KeyUse) -> _Traced:
        return self.probe_hosting(connection.provider, self._key(connection), None, on_use)

    def database(self, connection: StoredConnection, on_use: KeyUse) -> _Traced:
        return self.probe_database(connection.provider, self._key(connection), None, on_use)

    def runtime_host(self, connection: StoredConnection, on_use: KeyUse) -> _Traced | None:
        adapter = self.runtime_hosts.get(connection.provider)
        return _Traced(adapter, on_use) if adapter is not None else None

    def probe_hosting(
        self, provider: str, authorization: str, endpoint: str | None, on_use: KeyUse | None = None
    ) -> _Traced:
        adapter = self.hosting_adapters[provider]
        if authorization == "bad-key":
            return _Traced(FakeHosting(account=adapter.account, refuse=True), on_use or _ignore)
        return _Traced(adapter, on_use or _ignore)

    def probe_database(
        self, provider: str, authorization: str, endpoint: str | None, on_use: KeyUse | None = None
    ) -> _Traced:
        adapter = self.database_adapters[provider]
        if authorization == "bad-key":
            return _Traced(FakeDatabase(account=adapter.account, refuse=True), on_use or _ignore)
        return _Traced(adapter, on_use or _ignore)


def _ignore(_: str) -> None:
    return None


@dataclass
class FakeLinks:
    down: set[str] = field(default_factory=set)
    checked: list[str] = field(default_factory=list)

    async def check(self, url: str) -> LinkStatus:
        self.checked.append(url)
        return LinkStatus.DOWN if url in self.down else LinkStatus.UP


def deployment(
    reference: str,
    status: DeploymentStatus = DeploymentStatus.SUCCEEDED,
    *,
    age: timedelta = timedelta(days=3),
    commit: str | None = "abc123",
    author: str | None = None,
) -> DeploymentRecord:
    return DeploymentRecord(
        external_ref=reference,
        status=status,
        started_at=NOW - age,
        finished_at=None
        if status is DeploymentStatus.BUILDING
        else NOW - age + timedelta(minutes=1),
        commit_sha=commit,
        author=author,
    )


@dataclass
class FakeMailer:
    configured: bool = True
    sent: list[tuple[Recipient, RaisedAlert]] = field(default_factory=list)
    fail: bool = False

    async def send_alert(self, recipient: Recipient, alert: RaisedAlert) -> None:
        if self.fail:
            raise OSError("mail server unreachable")
        self.sent.append((recipient, alert))


@dataclass
class FakeMessenger:
    """A chat bot: people start it with a code; alerts and confirmations are recorded."""

    configured: bool = True
    starts: list[ChatStart] = field(default_factory=list)
    sent: list[tuple[ChatRecipient, RaisedAlert]] = field(default_factory=list)
    linked: list[ChatRecipient] = field(default_factory=list)
    fail: bool = False

    async def link_url(self, code: str) -> str:
        return f"https://chat.test/pono_bot?start={code}"

    async def started_chats(self) -> list[ChatStart]:
        if self.fail:
            raise ProviderUnavailableError("chat unreachable")
        return list(self.starts)

    def start(self, url: str, chat_id: str) -> None:
        """The person opens the link and presses Start."""
        self.starts.append(ChatStart(code=url.rsplit("=", 1)[1], chat_id=chat_id))

    async def send_linked(self, recipient: ChatRecipient) -> None:
        self.linked.append(recipient)

    async def send_alert(self, recipient: ChatRecipient, alert: RaisedAlert) -> None:
        if self.fail:
            raise ProviderUnavailableError("chat unreachable")
        self.sent.append((recipient, alert))


@dataclass
class World:
    code_host: FakeCodeHost
    factory: FakeFactory
    links: FakeLinks
    mailer: FakeMailer = field(default_factory=FakeMailer)
    messenger: FakeMessenger = field(default_factory=FakeMessenger)
    gate: FakeGate = field(default_factory=FakeGate)

    @property
    def providers(self) -> Providers:
        return Providers(
            code_host=self.code_host,
            factory=self.factory,
            manifests=RepositoryManifests(),
            links=self.links,
            mailer=self.mailer,
            messenger=self.messenger,
            console_url="http://console.test",
            gate=self.gate,
        )


def make_world() -> World:
    return World(
        code_host=FakeCodeHost(),
        factory=FakeFactory(
            hosting_adapters={"netlify": FakeHosting("alice-team"), "coolify": FakeHosting("cool")},
            database_adapters={"neon": FakeDatabase("alice-neon")},
        ),
        links=FakeLinks(),
    )


__all__ = [
    "NOW",
    "FakeCodeHost",
    "FakeDatabase",
    "FakeFactory",
    "FakeGate",
    "FakeHosting",
    "FakeLinks",
    "FakeRuntimeHost",
    "World",
    "awake_gate",
    "deployment",
    "make_world",
]
