import createClient from "openapi-fetch";
import type { paths } from "./schema";

export type { paths } from "./schema";

/**
 * A typed client for the Pono service. In the browser, `baseUrl` is the console's own origin:
 * calls go through the same-origin relay and carry the session cookie.
 */
export function createPonoClient(baseUrl = "") {
  return createClient<paths>({ baseUrl, credentials: "same-origin" });
}
