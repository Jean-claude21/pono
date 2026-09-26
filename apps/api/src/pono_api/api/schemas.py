"""Response and request bodies. They shape the OpenAPI the console's SDK is generated from."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from pydantic.alias_generators import to_camel

ProjectStateName = Literal["healthy", "active", "warning", "failing", "idle"]
EnvironmentKindName = Literal["production", "preview", "development"]
LinkStatusName = Literal["up", "down", "unknown", "missing"]
ResourceStatusName = Literal["found", "missing", "unknown"]
DeploymentStatusName = Literal["building", "succeeded", "failed", "cancelled"]
ManifestStatusName = Literal["present", "proposed", "absent"]


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Connection(ApiModel):
    id: UUID
    kind: Literal["code_host", "hosting", "database"]
    provider: str
    external_ref: str
    status: Literal["active", "expired", "revoked"]
    status_checked_at: datetime


class ConnectionRequest(ApiModel):
    kind: Literal["hosting", "database"]
    provider: str = Field(min_length=1)
    authorization: SecretStr = Field(
        min_length=1,
        json_schema_extra={"writeOnly": True},
        description="Provider-issued authorization; stored encrypted, never returned.",
    )
    endpoint: str | None = Field(
        None, pattern=r"^https?://\S+$", description="Base URL of a self-hosted provider."
    )


class Repository(ApiModel):
    full_name: str
    default_branch: str
    already_imported: bool
    project_id: UUID | None = Field(description="The project it already is, when imported.")


class ImportRequest(ApiModel):
    repository: str = Field(examples=["owner/name"])


class Environment(ApiModel):
    id: UUID
    kind: EnvironmentKindName
    branch: str | None
    url: str | None
    provider: str | None
    resource_status: ResourceStatusName
    link_status: LinkStatusName
    link_checked_at: datetime | None
    opened_at: datetime | None


class Deployment(ApiModel):
    environment_kind: EnvironmentKindName
    status: DeploymentStatusName
    commit_sha: str | None
    author: str | None
    started_at: datetime
    finished_at: datetime | None


class Quota(ApiModel):
    metric: Literal[
        "hosting_bandwidth_bytes", "db_compute_seconds", "db_storage_bytes", "db_transfer_bytes"
    ]
    used: float
    limit: float | None = Field(description="Null when the provider does not state it.")
    limit_source: Literal["account_plan", "free_tier_estimate"]
    ratio: float | None
    read_at: datetime


class ProjectSummary(ApiModel):
    id: UUID
    repository: str
    name: str
    state: ProjectStateName
    state_reason: str
    manifest_status: ManifestStatusName
    database_status: ResourceStatusName | None
    environments: list[Environment] = Field(
        description="Production, development and the most recent preview only."
    )
    last_deployment: Deployment | None
    quota: Quota | None
    last_activity_at: datetime | None
    refreshed_at: datetime | None
    stale: bool = Field(
        description="The last reading was incomplete; values date from refreshedAt."
    )


class Protection(ApiModel):
    status: Literal["protected", "unprotected", "unavailable_on_plan", "unknown"]
    branch: str | None = None
    checked_at: datetime | None = None


class RollbackRequest(ApiModel):
    id: UUID
    client_name: str
    requested_at: datetime


class ProjectDetail(ProjectSummary):
    manifest_proposal_url: str | None
    previews: list[Environment]
    quotas: list[Quota]
    protection: Protection
    can_rollback: bool = Field(
        description="False when production has no earlier successful deployment."
    )
    rollback_request: RollbackRequest | None = Field(
        None, description="An agent's rollback request waiting for a person (003 FR-011)."
    )


# --- agents (003) --------------------------------------------------------------------------------


class ConsentRequest(ApiModel):
    client_name: str
    scopes: list[Literal["pono:read", "pono:act"]]
    organization_name: str
    expires_at: datetime


class ConsentDecision(ApiModel):
    request: str = Field(min_length=16)
    access: Literal["read", "act"] | None = Field(None, description="Required to approve.")


class ConsentRedirect(ApiModel):
    redirect_url: str


class AgentGrant(ApiModel):
    id: UUID
    client_name: str
    access: Literal["read", "act"]
    granted_at: datetime
    last_used_at: datetime | None


# --- development runtime (004) -------------------------------------------------------------------

RuntimeStateName = Literal[
    "awaiting_files",
    "preparing",
    "starting",
    "ready",
    "sleeping",
    "stopped",
    "failed",
    "unreachable",
]


class RuntimeSave(ApiModel):
    commit_sha: str
    saved_at: datetime
    actor: str
    files: int


class RuntimeLimits(ApiModel):
    started: int
    max_started: int
    memory: str
    sleep_after_minutes: int


class Runtime(ApiModel):
    id: UUID
    state: RuntimeStateName
    reason: str | None
    url: str | None
    proposal_url: str | None
    development_branch: str
    awake: bool
    last_activity_at: datetime | None
    pending_writes: int
    conflicts: list[str]
    error_count: int
    last_save: RuntimeSave | None
    limits: RuntimeLimits


class RuntimeReport(ApiModel):
    source: Literal["compile", "browser"]
    message: str
    file: str | None = None
    line: int | None = None
    stack: str | None = None
    count: int
    first_at: datetime | None = None
    last_at: datetime | None = None
    resolved: bool


class RuntimeErrors(ApiModel):
    errors: list[RuntimeReport]
    live: bool = Field(description="False when the runtime did not answer: the last known errors.")


class FileWrite(ApiModel):
    path: str = Field(min_length=1, max_length=512)
    content: str | None = Field(None, description="UTF-8 text.")
    content_base64: str | None = Field(None, description="Any bytes, for a dropped file.")


class WriteResult(ApiModel):
    path: str
    pending_writes: int


class TicketRequest(ApiModel):
    return_: str | None = Field(
        None, alias="return", description="A local path of the application."
    )


class TicketUrl(ApiModel):
    url: str


# --- guarded release (002) ------------------------------------------------------------------------


class Finding(ApiModel):
    code: str
    file: str | None = None
    line: int | None = None
    operation: str | None = None
    url: str | None = None


class GuardResult(ApiModel):
    guard: Literal["secrets", "migrations", "preview"]
    status: Literal["pending", "passed", "failed"]
    reason: str | None = Field(None, description="Stable code, translated by the console.")
    findings: list[Finding] = Field(description="Where the guard failed; never a secret value.")
    checked_at: datetime


class Release(ApiModel):
    id: UUID
    change_number: int
    change_url: str
    title: str
    author: str
    head_sha: str
    head_branch: str | None
    verdict: Literal["evaluating", "refused", "awaiting_approval", "approved"]
    state: Literal["open", "merged", "closed"]
    opened_at: datetime
    evaluated_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
    guards: list[GuardResult]


class ApprovalRequest(ApiModel):
    head_sha: str = Field(min_length=7, description="The exact commit the person saw.")


class Rollback(ApiModel):
    id: UUID
    status: Literal["queued", "succeeded", "failed"]
    to_commit: str | None
    requested_at: datetime


class JournalEntry(ApiModel):
    id: UUID
    kind: str = Field(examples=["release.refused"])
    actor_kind: Literal["person", "agent", "pono"]
    actor: str | None
    head_sha: str | None
    change_number: int | None
    occurred_at: datetime
    detail: dict[str, object]


class Verdict(ApiModel):
    project_id: UUID
    code: str = Field(examples=["project.production_down"])


class Workshop(ApiModel):
    projects: list[ProjectSummary]
    counts: dict[ProjectStateName, int] = Field(
        description="Number of projects per state, shown on each filter (FR-027)."
    )
    verdicts: list[Verdict] = Field(description="What needs a decision, shown before the list.")


class Me(ApiModel):
    person_id: UUID
    login: str
    organization_id: UUID
    locale: Literal["fr", "en"] | None
    email: str | None = Field(description="Where quota alerts are sent; null when unknown.")
    alert_emails_enabled: bool = Field(description="False while the service has no mail server.")
    code_host_install_url: str | None
    chat_linked: bool = Field(description="True when the person linked a chat for quota alerts.")
    chat_alerts_enabled: bool = Field(
        description="False while the service has no chat bot configured."
    )


class ChatLink(ApiModel):
    url: str = Field(description="Opens the chat with the one-time code.")
    expires_at: datetime


__all__ = [
    "AgentGrant",
    "ApprovalRequest",
    "ChatLink",
    "Connection",
    "ConnectionRequest",
    "ConsentDecision",
    "ConsentRedirect",
    "ConsentRequest",
    "Deployment",
    "Environment",
    "FileWrite",
    "Finding",
    "GuardResult",
    "ImportRequest",
    "JournalEntry",
    "Me",
    "ProjectDetail",
    "ProjectSummary",
    "Protection",
    "Quota",
    "Release",
    "Repository",
    "Rollback",
    "RollbackRequest",
    "Runtime",
    "RuntimeErrors",
    "RuntimeLimits",
    "RuntimeReport",
    "RuntimeSave",
    "TicketRequest",
    "TicketUrl",
    "Verdict",
    "Workshop",
    "WriteResult",
]
