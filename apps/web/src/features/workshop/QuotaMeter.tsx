import type { CSSProperties } from "react";
import type { components } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, quantity } from "@/lib/format";

type Quota = components["schemas"]["Quota"];

const METRICS: Record<Quota["metric"], () => string> = {
  hosting_bandwidth_bytes: m.quota_metric_hosting_bandwidth_bytes,
  db_compute_seconds: m.quota_metric_db_compute_seconds,
  db_storage_bytes: m.quota_metric_db_storage_bytes,
  db_transfer_bytes: m.quota_metric_db_transfer_bytes,
};

const SOURCES: Record<Quota["limitSource"], () => string> = {
  account_plan: m.quota_source_account_plan,
  free_tier_estimate: m.quota_source_free_tier_estimate,
};

export function metricLabel(quota: Quota): string {
  return METRICS[quota.metric]();
}

export function sourceLabel(quota: Quota): string {
  return SOURCES[quota.limitSource]();
}

/** "102 / 300", with the bar coloured past 80 % and 95 % (FR-024, FR-025). */
export function QuotaMeter({ quota }: { quota: Quota }) {
  const ratio = quota.ratio ?? 0;
  const tone = ratio > 0.95 ? "meter crit" : ratio > 0.8 ? "meter warn" : "meter";
  const used = quantity(quota.used, quota.metric);
  const title = `${metricLabel(quota)} · ${sourceLabel(quota)} · ${dateTime(quota.readAt)}`;
  if (quota.limit === null || quota.limit === undefined) {
    return (
      <span className="meter" title={title}>
        <span className="figures">{used}</span>
        <small className="mute">{m.quota_limit_unknown()}</small>
      </span>
    );
  }
  return (
    <span
      className={tone}
      style={{ "--value": `${Math.min(100, Math.round(ratio * 100))}%` } as CSSProperties}
      title={title}
    >
      <span className="figures">
        {m.quota_of({ used, limit: quantity(quota.limit, quota.metric) })}
      </span>
      <i />
    </span>
  );
}
