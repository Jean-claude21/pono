import type { GuardResult, Protection, Release } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";

// Stable codes of the guarded release (002), turned into the active language (D-013).

type Message = () => string;
type MessageKey = keyof typeof m;

/** A catalog message looked up by a code the service returns; the code itself as a last resort. */
function byCode(prefix: string, code: string | null | undefined): string {
  if (!code) return "";
  const key = `${prefix}_${code.replaceAll(".", "_")}` as MessageKey;
  const message = m[key] as unknown as Message | undefined;
  return typeof message === "function" ? message() : code;
}

export function verdictLabel(verdict: Release["verdict"]): string {
  return {
    evaluating: m.release_verdict_evaluating,
    refused: m.release_verdict_refused,
    awaiting_approval: m.release_verdict_awaiting_approval,
    approved: m.release_verdict_approved,
  }[verdict]();
}

export function releaseStateLabel(release: Release): string {
  if (release.state === "merged") return m.release_state_merged();
  if (release.state === "closed") return m.release_state_closed();
  return verdictLabel(release.verdict);
}

export function guardName(guard: GuardResult["guard"]): string {
  return {
    secrets: m.guard_name_secrets,
    migrations: m.guard_name_migrations,
    preview: m.guard_name_preview,
  }[guard]();
}

export function guardStatusLabel(status: GuardResult["status"]): string {
  return {
    passed: m.guard_status_passed,
    failed: m.guard_status_failed,
    pending: m.guard_status_pending,
  }[status]();
}

export function guardReason(code: string | null | undefined): string {
  return byCode("guard", code);
}

export function operationLabel(operation: string | null | undefined): string {
  return byCode("operation", operation);
}

export function eventLabel(kind: string): string {
  return byCode("event", kind);
}

export function protectionLabel(protection: Protection): string {
  switch (protection.status) {
    case "protected":
      return m.protection_protected({ branch: protection.branch ?? "" });
    case "unprotected":
      return m.protection_unprotected();
    case "unavailable_on_plan":
      return m.protection_unavailable_on_plan();
    default:
      return m.protection_unknown();
  }
}

export function shortSha(sha: string | null | undefined): string {
  return sha ? sha.slice(0, 7) : "—";
}

/** Pending and approved read as settled; refused reads as a failure (D-011 verdict tones). */
export function verdictTone(verdict: Release["verdict"]): "failing" | "healthy" | "neutral" {
  if (verdict === "refused") return "failing";
  if (verdict === "approved") return "healthy";
  return "neutral";
}
