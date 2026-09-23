import * as m from "@/paraglide/messages.js";

type MessageKey = keyof typeof m;

/**
 * Translate a stable service error code (contracts/error-codes.md) into the active language.
 * `project.already_imported` maps to the catalog key `error_project_already_imported`.
 */
export function errorMessage(code: string): string {
  const key = `error_${code.replaceAll(".", "_")}`;
  if (key in m) {
    const message = m[key as MessageKey] as () => string;
    return message();
  }
  return m.error_unknown();
}
