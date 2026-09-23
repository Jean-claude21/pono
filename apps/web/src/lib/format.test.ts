import { describe, expect, it } from "vitest";
import { dateTime, integer, percent, quantity, relativeTime } from "./format";

// T080 — every date, duration and number follows the active language (FR-004).

const NOW = new Date("2026-09-23T12:00:00Z");
const ago = (seconds: number) => new Date(NOW.getTime() - seconds * 1000);

describe("relativeTime", () => {
  it.each([
    [30, "fr", "à l’instant"],
    [30, "en", "just now"],
    [12 * 60, "fr", "il y a 12 minutes"],
    [12 * 60, "en", "12 minutes ago"],
    [3 * 3600, "en", "3 hours ago"],
    [24 * 3600, "fr", "hier"],
    [9 * 24 * 3600, "fr", "il y a 9 jours"],
    [9 * 24 * 3600, "en", "9 days ago"],
    [21 * 24 * 3600, "fr", "il y a 3 semaines"],
    [62 * 24 * 3600, "en", "2 months ago"],
  ])("%is ago in %s reads %s", (seconds, locale, expected) => {
    expect(relativeTime(ago(seconds), NOW, locale)).toBe(expected);
  });
});

describe("numbers", () => {
  it("groups thousands the local way", () => {
    expect(integer(12345, "en")).toBe("12,345");
    expect(integer(12345, "fr").replace(/\s/g, " ")).toBe("12 345");
  });

  it("writes percentages the local way", () => {
    expect(percent(0.83, "en")).toBe("83%");
    expect(percent(0.83, "fr").replace(/\s/g, " ")).toBe("83 %");
  });

  it("writes quotas in their natural unit", () => {
    expect(quantity(31_875_072, "db_storage_bytes", "en")).toBe("32 MB");
    expect(quantity(2_733_676_870, "hosting_bandwidth_bytes", "fr").replace(/\s/g, " ")).toBe(
      "2,7 Go",
    );
    expect(quantity(360_000, "db_compute_seconds", "en")).toBe("100 hr");
    expect(quantity(7561, "db_compute_seconds", "fr").replace(/\s/g, " ")).toBe("2,1 h");
    expect(quantity(42, "other", "en")).toBe("42");
  });
});

describe("dateTime", () => {
  it("differs by language", () => {
    expect(dateTime(NOW, "en")).not.toBe(dateTime(NOW, "fr"));
  });
});
