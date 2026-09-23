import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

// T062 — both catalogs hold the same keys, and every stable code of the service has its message.

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const fr = JSON.parse(read("../../messages/fr.json")) as Record<string, string>;
const en = JSON.parse(read("../../messages/en.json")) as Record<string, string>;
const codes = ["001-project-workshop", "002-guarded-release"].flatMap((feature) =>
  [
    ...read(`../../../../specs/${feature}/contracts/error-codes.md`).matchAll(
      /^\| `([a-z_]+\.[a-z_*]+)` \|/gm,
    ),
  ].map((match) => match[1]),
);

describe("catalogs", () => {
  it("hold the same keys in French and English", () => {
    const keys = (catalog: Record<string, string>) =>
      Object.keys(catalog)
        .filter((key) => !key.startsWith("$"))
        .sort();
    expect(keys(en)).toEqual(keys(fr));
  });

  it("leave no message empty", () => {
    for (const catalog of [fr, en]) {
      for (const [key, value] of Object.entries(catalog)) {
        if (!key.startsWith("$")) expect(value.trim(), key).not.toBe("");
      }
    }
  });

  it("translate every stable code of the contract", () => {
    expect(codes.length).toBeGreaterThan(15);
    for (const code of codes) {
      if (code.includes("*")) continue;
      const key = `error_${code.replaceAll(".", "_")}`;
      const verdict = `verdict_${code.replaceAll(".", "_")}`;
      const guard = `guard_${code.replaceAll(".", "_")}`;
      expect(key in fr || verdict in fr || guard in fr, code).toBe(true);
      expect(key in en || verdict in en || guard in en, code).toBe(true);
    }
  });
});
