import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type { components, paths } from "./schema";

type Schemas = components["schemas"];
export type Me = Schemas["Me"];
export type Connection = Schemas["Connection"];
export type ConnectionRequest = Schemas["ConnectionRequest"];
export type Repository = Schemas["Repository"];
export type Environment = Schemas["Environment"];
export type Deployment = Schemas["Deployment"];
export type ProjectSummary = Schemas["ProjectSummary"];
export type ProjectDetail = Schemas["ProjectDetail"];
export type Verdict = Schemas["Verdict"];
export type Workshop = Schemas["Workshop"];
export type ProjectState = ProjectSummary["state"];
export type Release = Schemas["Release"];
export type GuardResult = Schemas["GuardResult"];
export type Finding = Schemas["Finding"];
export type Protection = Schemas["Protection"];
export type Rollback = Schemas["Rollback"];
export type JournalEntry = Schemas["JournalEntry"];

/** The body of every service error: a stable code, never prose (contracts/error-codes.md). */
export type ServiceError = { error: { code: string; field?: string } };

/**
 * A typed client for the Pono service. In the browser, `baseUrl` is the console's own origin:
 * calls go through the same-origin relay and carry the session cookie.
 */
export function createPonoClient(baseUrl = "") {
  return createClient<paths>({ baseUrl, credentials: "same-origin" });
}

/** The error code of a failed call, whatever its shape. */
export function errorCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "error" in error) {
    const inner = (error as ServiceError).error;
    if (inner && typeof inner.code === "string") return inner.code;
  }
  return "unknown";
}
