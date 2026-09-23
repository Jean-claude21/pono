"""Provider ports (constitution III). Adapters live in infrastructure, behind these contracts.

Every provider answer is plain data. A provider that cannot answer raises
`ProviderUnavailableError`; one that refuses the credential raises `ProviderAuthorizationError`.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pono_api.domain.manifest import (
    ImportedFrom,
    ManifestDatabase,
    ManifestEnvironment,
    ProjectManifest,
    ProviderRef,
)
from pono_api.domain.projects import (
    ConnectionKind,
    DeploymentStatus,
    EnvironmentKind,
    LinkStatus,
    ResourceStatus,
)
from pono_api.domain.quotas import QuotaReading


class ProviderUnavailableError(RuntimeError):
    """The provider did not answer in a trustworthy way; the previous state is kept."""


class ProviderAuthorizationError(RuntimeError):
    """The provider refused the credential: expired, revoked or never valid."""


class ForbiddenWriteError(PermissionError):
    """A write outside the proposal branches was attempted (FR-029). Never reaches a provider."""


# --- Code host --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    full_name: str
    default_branch: str


ProposalState = Literal["open", "merged", "closed"]


class CodeHost(Protocol):
    """Reads repositories and proposes changes. It has no merge operation, by design."""

    @property
    def provider(self) -> str:
        """The adapter id stored on the connection; opaque to the domain."""

    async def find_installation(self, account_id: str) -> str | None:
        """The installation on the person's own account, if they installed Pono there."""

    async def installation_active(self, installation_id: str) -> bool: ...

    async def revoke_installation(self, installation_id: str) -> None: ...

    async def list_repositories(self, installation_id: str) -> list[RepositoryInfo]: ...

    async def read_file(
        self, installation_id: str, repository: str, path: str, ref: str | None = None
    ) -> str | None:
        """File content, or None when the file does not exist."""

    async def last_commit_at(self, installation_id: str, repository: str) -> datetime | None:
        """The last commit on any branch, Pono's own proposal branches excepted."""

    async def commit_author(
        self, installation_id: str, repository: str, commit_sha: str
    ) -> str | None: ...

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
        """Commit one file on a proposal branch and open a pull request; returns its URL."""

    async def proposal_state(self, installation_id: str, proposal_url: str) -> ProposalState: ...


# --- Hosting and database ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeploymentRecord:
    external_ref: str
    status: DeploymentStatus
    started_at: datetime
    finished_at: datetime | None = None
    commit_sha: str | None = None
    author: str | None = None


@dataclass(frozen=True, slots=True)
class PreviewRecord:
    external_ref: str
    url: str
    opened_at: datetime
    branch: str | None = None
    review_url: str | None = None
    """The change request the preview belongs to; a closed one hides the preview."""


@dataclass(frozen=True, slots=True)
class DetectedEnvironment:
    """A site or application a provider links to the repository, for the manifest pre-fill."""

    kind: EnvironmentKind
    ref: str
    url: str | None = None
    branch: str | None = None


@dataclass(frozen=True, slots=True)
class HostedEnvironment:
    """What the provider says about one environment right now."""

    status: ResourceStatus
    url: str | None = None
    deployments: tuple[DeploymentRecord, ...] = ()
    previews: tuple[PreviewRecord, ...] = ()


class HostingProvider(Protocol):
    async def verify(self) -> str:
        """Check the credential and return the account reference it grants."""

    async def detect(
        self, repository: str, name: str, default_branch: str
    ) -> list[DetectedEnvironment]: ...

    async def read_environment(
        self, ref: str, kind: EnvironmentKind, branch: str | None
    ) -> HostedEnvironment: ...

    async def read_quotas(self) -> list[QuotaReading]:
        """Account-level consumption; empty for a host with no quota (a server of one's own)."""


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    status: ResourceStatus
    branches: tuple[str, ...] = ()


class DatabaseProvider(Protocol):
    async def verify(self) -> str: ...

    async def find_project(self, name: str) -> str | None: ...

    async def read_project(self, ref: str) -> DatabaseSnapshot: ...

    async def read_quotas(self, ref: str) -> list[QuotaReading]:
        """Consumption of one database project in its current billing period."""


# --- Manifests --------------------------------------------------------------------------------


@dataclass(slots=True)
class ManifestDraft:
    """What an existing manifest format says, before provider detection completes it."""

    source: ImportedFrom
    name: str
    environments: list[ManifestEnvironment] = field(default_factory=list)
    database: ManifestDatabase | None = None
    database_provider: str | None = None
    """A database named without its reference: detection looks it up by project name."""
    database_branches: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class Detection:
    provider: str
    environment: DetectedEnvironment


class ManifestReader(Protocol):
    """Reads the formats already present in repositories and pre-fills a Pono manifest."""

    @property
    def legacy_paths(self) -> tuple[str, ...]:
        """Paths of the formats Pono can read, in order of precedence (research R-06)."""

    def read(self, path: str, content: str, repository: RepositoryInfo) -> ManifestDraft | None:
        """None when the file does not hold a usable manifest."""

    def prefill(
        self,
        repository: RepositoryInfo,
        draft: ManifestDraft | None,
        detections: list[Detection],
        database: ProviderRef | None,
    ) -> ProjectManifest: ...


# --- Alerts -----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Recipient:
    email: str
    locale: str | None


@dataclass(frozen=True, slots=True)
class RaisedAlert:
    project_name: str | None
    metric: str
    threshold: int
    used: float
    limit: float
    limit_source: str


class Mailer(Protocol):
    """Sends alert emails. The adapter writes the words, in the recipient's language."""

    @property
    def configured(self) -> bool: ...

    async def send_alert(self, recipient: Recipient, alert: RaisedAlert) -> None: ...


# --- Links ------------------------------------------------------------------------------------


class LinkChecker(Protocol):
    async def check(self, url: str) -> LinkStatus: ...


# --- Resolution of adapters from stored connections -------------------------------------------


KeyUse = Callable[[str], None]
"""Called with an action name each time a permanent provider key is used (FR-011, D-007)."""


@dataclass(frozen=True, slots=True)
class StoredConnection:
    id: UUID
    kind: ConnectionKind
    provider: str
    external_ref: str
    endpoint: str | None
    secret_ciphertext: bytes | None
    status: str


@dataclass(slots=True)
class KeyUseLog:
    """Collects key uses during a unit of work; the use case writes them as connection events."""

    entries: list[tuple[UUID, str]] = field(default_factory=list)

    def recorder(self, connection_id: UUID) -> KeyUse:
        def record(action: str) -> None:
            self.entries.append((connection_id, action))

        return record


class ProviderFactory(Protocol):
    """Builds adapters. Credentials are decrypted inside, never handed to the application."""

    def supports(self, kind: ConnectionKind, provider: str) -> bool: ...

    def hosting(self, connection: StoredConnection, on_use: KeyUse) -> HostingProvider: ...

    def database(self, connection: StoredConnection, on_use: KeyUse) -> DatabaseProvider: ...

    def probe_hosting(
        self, provider: str, authorization: str, endpoint: str | None
    ) -> HostingProvider: ...

    def probe_database(
        self, provider: str, authorization: str, endpoint: str | None
    ) -> DatabaseProvider: ...

    def seal(self, authorization: str) -> bytes: ...


__all__ = [
    "CodeHost",
    "DatabaseProvider",
    "DatabaseSnapshot",
    "DeploymentRecord",
    "DetectedEnvironment",
    "Detection",
    "ForbiddenWriteError",
    "HostedEnvironment",
    "HostingProvider",
    "KeyUse",
    "KeyUseLog",
    "LinkChecker",
    "Mailer",
    "ManifestDraft",
    "ManifestReader",
    "PreviewRecord",
    "ProposalState",
    "ProviderAuthorizationError",
    "ProviderFactory",
    "ProviderUnavailableError",
    "RaisedAlert",
    "Recipient",
    "RepositoryInfo",
    "StoredConnection",
]
