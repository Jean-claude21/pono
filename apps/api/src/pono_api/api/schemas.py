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


class ProjectDetail(ProjectSummary):
    manifest_proposal_url: str | None
    previews: list[Environment]
    quotas: list[Quota]


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


__all__ = [
    "Connection",
    "ConnectionRequest",
    "Deployment",
    "Environment",
    "ImportRequest",
    "Me",
    "ProjectDetail",
    "ProjectSummary",
    "Quota",
    "Repository",
    "Verdict",
    "Workshop",
]
