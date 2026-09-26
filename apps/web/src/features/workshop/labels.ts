import type { Deployment, Environment, ProjectState } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";

// Stable codes from the service, turned into the active language. Nothing here is prose written
// in a component: every label comes from the catalogs (D-013).

export const STATES: ProjectState[] = ["healthy", "active", "warning", "failing", "idle"];

export function stateLabel(state: ProjectState): string {
  return {
    healthy: m.state_healthy,
    active: m.state_active,
    warning: m.state_warning,
    failing: m.state_failing,
    idle: m.state_idle,
  }[state]();
}

export function countLabel(state: ProjectState): string {
  return {
    healthy: m.count_healthy,
    active: m.count_active,
    warning: m.count_warning,
    failing: m.count_failing,
    idle: m.count_idle,
  }[state]();
}

export function filterLabel(state: ProjectState): string {
  return {
    healthy: m.filter_healthy,
    active: m.filter_active,
    warning: m.filter_warning,
    failing: m.filter_failing,
    idle: m.filter_idle,
  }[state]();
}

const REASONS: Record<string, () => string> = {
  production_down: m.reason_production_down,
  deployment_failed: m.reason_deployment_failed,
  quota_warning: m.reason_quota_warning,
  connection_expired: m.reason_connection_expired,
  deployment_in_progress: m.reason_deployment_in_progress,
  recent_activity: m.reason_recent_activity,
  no_recent_activity: m.reason_no_recent_activity,
  nominal: m.reason_nominal,
};

export function reasonLabel(reason: string): string {
  return (REASONS[reason] ?? m.reason_nominal)();
}

const VERDICTS: Record<string, [(input: { name: string }) => string, () => string]> = {
  "project.production_down": [
    m.verdict_project_production_down,
    m.verdict_project_production_down_body,
  ],
  "project.deployment_failed": [
    m.verdict_project_deployment_failed,
    m.verdict_project_deployment_failed_body,
  ],
  "connection.expired": [m.verdict_connection_expired, m.verdict_connection_expired_body],
  "project.manifest_proposed": [
    m.verdict_project_manifest_proposed,
    m.verdict_project_manifest_proposed_body,
  ],
  "project.quota_warning": [m.verdict_project_quota_warning, m.verdict_project_quota_warning_body],
  "project.quota_critical": [
    m.verdict_project_quota_critical,
    m.verdict_project_quota_critical_body,
  ],
  "release.refused": [m.verdict_release_refused, m.verdict_release_refused_body],
  "release.awaiting_approval": [
    m.verdict_release_awaiting_approval,
    m.verdict_release_awaiting_approval_body,
  ],
  "project.unprotected": [m.verdict_project_unprotected, m.verdict_project_unprotected_body],
  "project.protection_unavailable": [
    m.verdict_project_protection_unavailable,
    m.verdict_project_protection_unavailable_body,
  ],
  "release.merged_without_approval": [
    m.verdict_release_merged_without_approval,
    m.verdict_release_merged_without_approval_body,
  ],
  "rollback.failed": [m.verdict_rollback_failed, m.verdict_rollback_failed_body],
  "rollback.requested": [m.verdict_rollback_requested, m.verdict_rollback_requested_body],
};

// Decisions waiting for the person wash green; everything else is a failure to look at.
const DECISIONS = new Set([
  "project.manifest_proposed",
  "release.awaiting_approval",
  "rollback.requested",
]);

export function verdictText(code: string, name: string): { title: string; body: string } {
  const [title, body] = VERDICTS[code] ?? VERDICTS["project.production_down"];
  return { title: title({ name }), body: body() };
}

/** Failing verdicts wash red; decisions that are not failures wash green. */
export function verdictTone(code: string): "failing" | "healthy" {
  return DECISIONS.has(code) ? "healthy" : "failing";
}

export function environmentLabel(kind: Environment["kind"]): string {
  return { production: m.env_production, preview: m.env_preview, development: m.env_development }[
    kind
  ]();
}

export function linkLabel(status: Environment["linkStatus"]): string {
  return { up: m.link_up, down: m.link_down, unknown: m.link_unknown, missing: m.link_missing }[
    status
  ]();
}

export function deploymentStatusLabel(status: Deployment["status"]): string {
  return {
    building: m.deployment_status_building,
    succeeded: m.deployment_status_succeeded,
    failed: m.deployment_status_failed,
    cancelled: m.deployment_status_cancelled,
  }[status]();
}

export function providerLabel(provider: string | null | undefined): string {
  const names: Record<string, () => string> = {
    github: m.provider_github,
    netlify: m.provider_netlify,
    coolify: m.provider_coolify,
    neon: m.provider_neon,
  };
  return provider ? (names[provider]?.() ?? provider) : "";
}

/** The host name of an address, for compact display. */
export function hostOf(url: string | null | undefined): string {
  if (!url) return "";
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
