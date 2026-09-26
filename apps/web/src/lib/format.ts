import { getLocale } from "@/paraglide/runtime.js";
import * as m from "@/paraglide/messages.js";

// Every date, duration and number goes through Intl with the active language (FR-004).

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  // Weeks only from two on: "9 days ago" is more useful than "last week".
  ["week", 14 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

/** "il y a 12 min" / "12 min ago". Under a minute reads "just now". */
export function relativeTime(
  value: string | Date,
  now: Date = new Date(),
  locale: string = getLocale(),
): string {
  const moment = typeof value === "string" ? new Date(value) : value;
  const seconds = Math.round((moment.getTime() - now.getTime()) / 1000);
  const absolute = Math.abs(seconds);
  const format = new Intl.RelativeTimeFormat(locale, { numeric: "auto", style: "long" });
  for (const [unit, threshold] of UNITS) {
    if (absolute >= threshold) {
      const size = unit === "week" ? 7 * 24 * 3600 : threshold;
      return format.format(Math.round(seconds / size), unit);
    }
  }
  return m.time_now({}, { locale: locale as "fr" | "en" });
}

/** A full date and time, for tooltips and detail views. */
export function dateTime(value: string | Date, locale: string = getLocale()): string {
  const moment = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
    moment,
  );
}

/** A calendar day, without the time. */
export function calendarDay(value: string | Date, locale: string = getLocale()): string {
  const moment = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat(locale, { dateStyle: "long" }).format(moment);
}

export function integer(value: number, locale: string = getLocale()): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(value);
}

/** A ratio between 0 and 1, shown as a percentage. */
export function percent(ratio: number, locale: string = getLocale()): string {
  return new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 0 }).format(
    ratio,
  );
}

/** A quota amount in its natural unit: bytes as MB or GB, seconds as hours. */
export function quantity(value: number, metric: string, locale: string = getLocale()): string {
  if (metric.endsWith("_bytes")) {
    const gigabytes = value / 1e9;
    const [amount, unit] = gigabytes >= 1 ? [gigabytes, "gigabyte"] : [value / 1e6, "megabyte"];
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit,
      maximumFractionDigits: amount >= 10 ? 0 : 1,
    }).format(amount);
  }
  if (metric.endsWith("_seconds")) {
    const hours = value / 3600;
    return new Intl.NumberFormat(locale, {
      style: "unit",
      unit: "hour",
      maximumFractionDigits: hours >= 10 ? 0 : 1,
    }).format(hours);
  }
  return integer(value, locale);
}
