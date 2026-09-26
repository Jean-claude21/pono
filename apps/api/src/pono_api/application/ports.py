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
from pono_api.domain.releases import ProtectionStatus


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
CheckState = Literal["pending", "failure", "success"]


@dataclass(frozen=True, slots=True)
class ChangeRequest:
    """A proposed change towards a branch, at its current head (002 FR-001)."""

    number: int
    url: str
    title: str
    author: str
    author_is_agent: bool
    head_sha: str
    head_branch: str | None
    base_branch: str
    state: ProposalState


@dataclass(frozen=True, slots=True)
class ChangedFile:
    path: str
    status: str
    """added, modified, removed or renamed."""
    patch: str | None
    """The unified diff; None when the code host does not give it (binary or too large)."""
    binary: bool = False


class ProtectionRefusedError(RuntimeError):
    """The code host refused to protect the branch; `code` is a stable error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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

    # --- guarded release (002) ----------------------------------------------------------------

    async def list_changes(
        self, installation_id: str, repository: str, base_branch: str
    ) -> list[ChangeRequest]:
        """Open changes towards `base_branch`."""
        ...

    async def read_change(
        self, installation_id: str, repository: str, number: int
    ) -> ChangeRequest: ...

    async def change_files(
        self, installation_id: str, repository: str, number: int
    ) -> list[ChangedFile]: ...

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
        """The one check production branches require; a bounded write (002 research R-01)."""
        ...

    async def read_protection(
        self, installation_id: str, repository: str, branch: str
    ) -> ProtectionStatus: ...

    async def apply_protection(self, installation_id: str, repository: str, branch: str) -> None:
        """Protect a production branch (002 FR-015). Raises `ProtectionRefusedError` when the
        code host refuses."""
        ...

    # --- development runtime (004) ------------------------------------------------------------

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
        """Commit several files on a proposal branch and open one pull request towards `base`."""
        ...

    async def branch_head(self, installation_id: str, repository: str, branch: str) -> str: ...

    def clone_url(self, repository: str) -> str:
        """The address a deploy key clones the repository from."""
        ...

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
        """The third bounded write (D-019): one commit on the named development branch, never the
        default branch, never forced. Paths the branch changed since `expected_head` are returned
        as conflicts and left out of the commit."""
        ...

    async def add_deploy_key(
        self, installation_id: str, repository: str, *, title: str, public_key: str
    ) -> str:
        """A read-only deploy key for the runtime; returns its reference."""
        ...

    async def remove_deploy_key(
        self, installation_id: str, repository: str, key_ref: str
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class FileChange:
    path: str
    content: bytes | None
    """None deletes the file."""


@dataclass(frozen=True, slots=True)
class DevelopmentCommit:
    commit_sha: str | None
    """None when every change was left out as a conflict."""
    head: str
    """The branch head after the write."""
    conflicts: tuple[str, ...] = ()


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
    live_commit: str | None = None
    """The commit production actually serves, when the host says it (002 rollback)."""


PreviewStatus = Literal["absent", "building", "ready", "failed"]


@dataclass(frozen=True, slots=True)
class PreviewState:
    """The preview of one change at one commit (002 research R-05)."""

    status: PreviewStatus
    url: str | None = None
    started_at: datetime | None = None


class RollbackUnsupportedError(RuntimeError):
    """The host cannot bring this deployment back (no image left, no such deployment)."""


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

    async def find_preview(self, ref: str, change_number: int, head_sha: str) -> PreviewState: ...

    async def rollback(self, ref: str, target: DeploymentRecord) -> str:
        """Bring production back to `target`; returns the new deployment reference. The only write
        of a hosting adapter (002 research R-08)."""
        ...


@dataclass(frozen=True, slots=True)
class DatabaseSnapshot:
    status: ResourceStatus
    branches: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DevelopmentDatabase:
    """Where a runtime connects (004 research R-03). The address carries a password: it goes to
    the runtime's host and is never stored by Pono."""

    url: str
    host: str
    production_host: str | None


class DevelopmentDatabaseError(RuntimeError):
    """The development branch is missing, or is the production branch; `code` is stable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DatabaseProvider(Protocol):
    async def verify(self) -> str: ...

    async def find_project(self, name: str) -> str | None: ...

    async def read_project(self, ref: str) -> DatabaseSnapshot: ...

    async def read_quotas(self, ref: str) -> list[QuotaReading]:
        """Consumption of one database project in its current billing period."""

    async def development_target(
        self, ref: str, development_branch: str, production_branch: str | None
    ) -> DevelopmentDatabase:
        """The development branch's address; `DevelopmentDatabaseError` when it is missing or is
        the production branch."""
        ...


# --- Development runtime (004) ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    """What the host needs to create a project's runtime."""

    name: str
    clone_url: str
    """The repository's SSH address, as the code host gives it."""
    branch: str
    private_key: str
    """The read-only deploy key's private half; handed to the host, never stored by Pono."""
    variables: dict[str, str]
    memory: str
    near_ref: str | None = None
    """An application of the project the host already runs: its server is preferred."""


@dataclass(frozen=True, slots=True)
class RuntimeHandle:
    ref: str
    url: str
    key_ref: str


HostRuntimeStatus = Literal["starting", "running", "stopped", "failed", "missing"]


class RuntimeHostError(RuntimeError):
    """The host cannot create the runtime as asked; `code` is stable (e.g. server_ambiguous)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RuntimeHost(Protocol):
    """The runtime's application at the person's host, and nothing else (D-019)."""

    async def create_runtime(self, spec: RuntimeSpec) -> RuntimeHandle: ...

    async def start_runtime(self, ref: str) -> None: ...

    async def stop_runtime(self, ref: str) -> None: ...

    async def delete_runtime(self, ref: str, key_ref: str | None) -> None: ...

    async def runtime_status(self, ref: str) -> HostRuntimeStatus: ...


@dataclass(frozen=True, slots=True)
class GateStatus:
    """What the runtime's gate says about itself."""

    awake: bool
    last_activity_at: datetime | None
    head: str | None
    conflicts: tuple[str, ...]
    errors: tuple[dict[str, object], ...]
    database_host: str | None


class RuntimeUnreachableError(RuntimeError):
    """The gate did not answer in a trustworthy way."""


class GateRefusedError(RuntimeError):
    """The gate refused a write; `code` is stable."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RuntimeCredentials:
    token: str
    """Shared with the gate through the host's variables; stored by Pono only sealed."""
    sealed_token: bytes
    private_key: str
    public_key: str


class RuntimeGate(Protocol):
    """Talks to a runtime's gate. The token is unsealed inside, never handed to the application
    once stored."""

    def new_credentials(self) -> RuntimeCredentials: ...

    def ticket(self, sealed_token: bytes, runtime_id: UUID) -> str: ...

    async def status(self, url: str, sealed_token: bytes) -> GateStatus: ...

    async def write(
        self, url: str, sealed_token: bytes, path: str, content: bytes | None
    ) -> None: ...


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


@dataclass(frozen=True, slots=True)
class ChatRecipient:
    chat_id: str
    locale: str | None


@dataclass(frozen=True, slots=True)
class ChatStart:
    """A private chat that was started with a code."""

    code: str
    chat_id: str


class ChatMessenger(Protocol):
    """Sends alerts to a chat the person linked themselves (D-015). The adapter writes the words.

    Linking needs no public address: the link carries a one-time code, the person sends it by
    starting the chat, and `started_chats` returns the codes the bot received.
    """

    @property
    def configured(self) -> bool: ...

    async def link_url(self, code: str) -> str:
        """Opens the chat so that starting it sends the code back."""
        ...

    async def started_chats(self) -> list[ChatStart]:
        """Private chats recently started with a code, oldest first."""
        ...

    async def send_linked(self, recipient: ChatRecipient) -> None: ...

    async def send_alert(self, recipient: ChatRecipient, alert: RaisedAlert) -> None: ...


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

    def runtime_host(self, connection: StoredConnection, on_use: KeyUse) -> RuntimeHost | None:
        """The connection's runtime host, or None when its provider cannot run one (004)."""
        ...

    def probe_hosting(
        self, provider: str, authorization: str, endpoint: str | None
    ) -> HostingProvider: ...

    def probe_database(
        self, provider: str, authorization: str, endpoint: str | None
    ) -> DatabaseProvider: ...

    def seal(self, authorization: str) -> bytes: ...


__all__ = [
    "ChangeRequest",
    "ChangedFile",
    "ChatMessenger",
    "ChatRecipient",
    "ChatStart",
    "CheckState",
    "CodeHost",
    "DatabaseProvider",
    "DatabaseSnapshot",
    "DeploymentRecord",
    "DetectedEnvironment",
    "Detection",
    "DevelopmentCommit",
    "DevelopmentDatabase",
    "DevelopmentDatabaseError",
    "FileChange",
    "ForbiddenWriteError",
    "GateRefusedError",
    "GateStatus",
    "HostRuntimeStatus",
    "HostedEnvironment",
    "HostingProvider",
    "KeyUse",
    "KeyUseLog",
    "LinkChecker",
    "Mailer",
    "ManifestDraft",
    "ManifestReader",
    "PreviewRecord",
    "PreviewState",
    "PreviewStatus",
    "ProposalState",
    "ProtectionRefusedError",
    "ProviderAuthorizationError",
    "ProviderFactory",
    "ProviderUnavailableError",
    "RaisedAlert",
    "Recipient",
    "RepositoryInfo",
    "RollbackUnsupportedError",
    "RuntimeCredentials",
    "RuntimeGate",
    "RuntimeHandle",
    "RuntimeHost",
    "RuntimeHostError",
    "RuntimeSpec",
    "RuntimeUnreachableError",
    "StoredConnection",
]
