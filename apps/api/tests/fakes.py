"""In-memory providers for tests: no network, fully scripted, recording what they are asked."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from pono_api.application.ports import (
    DatabaseSnapshot,
    DeploymentRecord,
    DetectedEnvironment,
    HostedEnvironment,
    KeyUse,
    ProposalState,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RepositoryInfo,
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
from pono_api.infrastructure.manifests import RepositoryManifests

NOW = datetime.now(UTC)


@dataclass
class FakeCodeHost:
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


@dataclass
class FakeHosting:
    account: str
    detected: dict[str, list[DetectedEnvironment]] = field(default_factory=dict)
    environments: dict[str, HostedEnvironment] = field(default_factory=dict)
    refuse: bool = False
    unavailable: bool = False

    def _answer(self) -> None:
        if self.refuse:
            raise ProviderAuthorizationError("refused")
        if self.unavailable:
            raise ProviderUnavailableError("down")

    async def verify(self) -> str:
        self._answer()
        return self.account

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
class World:
    code_host: FakeCodeHost
    factory: FakeFactory
    links: FakeLinks

    @property
    def providers(self) -> Providers:
        return Providers(
            code_host=self.code_host,
            factory=self.factory,
            manifests=RepositoryManifests(),
            links=self.links,
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
    "FakeHosting",
    "FakeLinks",
    "World",
    "deployment",
    "make_world",
]
