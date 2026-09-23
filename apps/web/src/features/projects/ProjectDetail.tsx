import { useState } from "react";
import { Link, useRouter } from "@tanstack/react-router";
import {
  createPonoClient,
  errorCode,
  type Environment,
  type ProjectDetail as Detail,
  type Release,
} from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";
import {
  deploymentStatusLabel,
  environmentLabel,
  hostOf,
  linkLabel,
  providerLabel,
  reasonLabel,
  stateLabel,
} from "@/features/workshop/labels";
import { QuotaMeter, metricLabel, sourceLabel } from "@/features/workshop/QuotaMeter";
import { Releases } from "@/features/releases/Releases";
import { protectionLabel } from "@/features/releases/labels";

const MANIFEST: Record<Detail["manifestStatus"], () => string> = {
  present: m.manifest_present,
  proposed: m.manifest_proposed,
  absent: m.manifest_absent,
};

const DATABASE: Record<string, () => string> = {
  found: m.database_found,
  missing: m.database_missing,
  unknown: m.database_unknown,
};

/** A project as it really is: every environment, every open preview, and where it comes from. */
export function ProjectDetail({ project, releases }: { project: Detail; releases: Release[] }) {
  const router = useRouter();
  const [queued, setQueued] = useState(false);
  const [proposing, setProposing] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [protecting, setProtecting] = useState(false);
  const [confirmingRollback, setConfirmingRollback] = useState(false);
  const [rollbackQueued, setRollbackQueued] = useState(false);
  const params = { params: { path: { project_id: project.id } } };

  async function protect() {
    setProtecting(true);
    setFailure(null);
    const { error } = await createPonoClient().POST(
      "/api/v1/projects/{project_id}/protection",
      params,
    );
    setProtecting(false);
    if (error) {
      setFailure(errorCode(error));
      return;
    }
    await router.invalidate();
  }

  async function rollBack() {
    setConfirmingRollback(false);
    setFailure(null);
    const { error } = await createPonoClient().POST("/api/v1/projects/{project_id}/rollback", params);
    if (error) {
      setFailure(errorCode(error));
      return;
    }
    setRollbackQueued(true);
    await router.invalidate();
  }

  async function proposeAgain() {
    setProposing(true);
    setFailure(null);
    const { error } = await createPonoClient().POST(
      "/api/v1/projects/{project_id}/manifest-proposal",
      { params: { path: { project_id: project.id } } },
    );
    setProposing(false);
    if (error) {
      setFailure(errorCode(error));
      return;
    }
    await router.invalidate();
  }

  async function refresh() {
    setQueued(true);
    await createPonoClient().POST("/api/v1/projects/{project_id}/refresh", {
      params: { path: { project_id: project.id } },
    });
    // The reading runs in the background; show its result as soon as it lands.
    window.setTimeout(() => {
      setQueued(false);
      void router.invalidate();
    }, 4000);
  }

  const standing = project.environments.filter((environment) => environment.kind !== "preview");
  const deployment = project.lastDeployment;

  return (
    <>
      <Link className="back" to="/workshop">
        ← {m.detail_back()}
      </Link>
      <div className="topline" style={{ marginTop: 12 }}>
        <div>
          <h1>{project.name}</h1>
          <div className="counts mute">
            <span className={`state state-${project.state}`}>{stateLabel(project.state)}</span>
            <span>{reasonLabel(project.stateReason)}</span>
            <span title={project.refreshedAt ? dateTime(project.refreshedAt) : undefined}>
              {project.refreshedAt
                ? m.refreshed_when({ when: relativeTime(project.refreshedAt) })
                : m.never_refreshed()}
            </span>
          </div>
        </div>
        <div className="topline-actions">
          <Link
            className="btn btn-ghost btn-sm"
            to="/workshop/projects/$projectId/journal"
            params={{ projectId: project.id }}
          >
            {m.journal_link()}
          </Link>
          {project.canRollback ? (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setConfirmingRollback(true)}
              disabled={confirmingRollback || rollbackQueued}
            >
              {m.rollback_action()}
            </button>
          ) : null}
          <button type="button" className="btn btn-ghost btn-sm" onClick={refresh} disabled={queued}>
            {m.detail_refresh()}
          </button>
        </div>
      </div>

      {confirmingRollback ? (
        <div className="verdict" role="alertdialog" style={{ marginTop: 20 }}>
          <p>{m.rollback_confirm_body()}</p>
          <div className="topline-actions">
            <button type="button" className="btn btn-primary btn-sm" onClick={rollBack}>
              {m.rollback_confirm()}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => setConfirmingRollback(false)}
            >
              {m.rollback_cancel()}
            </button>
          </div>
        </div>
      ) : null}
      {rollbackQueued ? <p className="notice">{m.rollback_queued()}</p> : null}

      {queued ? <p className="notice">{m.detail_refresh_queued()}</p> : null}
      {failure ? (
        <div className="verdict" role="alert" style={{ marginTop: 20 }}>
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}
      {project.stale && project.refreshedAt ? (
        <p className="notice warning">
          {m.detail_stale({ when: dateTime(project.refreshedAt) })}
        </p>
      ) : null}

      <dl className="facts">
        <div className="fact">
          <dt>{m.detail_repository()}</dt>
          <dd className="figures" style={{ fontSize: 14 }}>
            {project.repository}
          </dd>
        </div>
        <div className="fact">
          <dt>{m.detail_last_deployment()}</dt>
          <dd>
            {deployment ? (
              <span title={dateTime(deployment.startedAt)}>
                {deploymentStatusLabel(deployment.status)} · {relativeTime(deployment.startedAt)}
                {deployment.author ? <span className="mute"> · {deployment.author}</span> : null}
              </span>
            ) : (
              <span className="mute">{m.deployment_none()}</span>
            )}
          </dd>
        </div>
        <div className="fact">
          <dt>{m.detail_manifest()}</dt>
          <dd>
            {MANIFEST[project.manifestStatus]()}
            {project.manifestProposalUrl && project.manifestStatus === "proposed" ? (
              <>
                {" "}
                <a href={project.manifestProposalUrl} target="_blank" rel="noreferrer">
                  {m.manifest_open_proposal()}
                </a>
              </>
            ) : null}
            {project.manifestStatus === "absent" ? (
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={proposeAgain}
                  disabled={proposing}
                >
                  {proposing ? m.manifest_proposing() : m.manifest_propose_again()}
                </button>
              </div>
            ) : null}
          </dd>
        </div>
        <div className="fact">
          <dt>{m.detail_protection()}</dt>
          <dd>
            <span className={`protection ${project.protection.status}`}>
              {protectionLabel(project.protection)}
            </span>
            {project.protection.status === "unprotected" ? (
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={protect}
                  disabled={protecting}
                >
                  {protecting ? m.protection_applying() : m.protection_apply()}
                </button>
              </div>
            ) : null}
          </dd>
        </div>
        <div className="fact">
          <dt>{m.detail_database()}</dt>
          <dd>
            {project.databaseStatus
              ? (DATABASE[project.databaseStatus] ?? m.database_unknown)()
              : m.database_none()}
          </dd>
        </div>
      </dl>

      <Releases projectId={project.id} releases={releases} />

      <h2 className="mono-label section-title">{m.detail_environments()}</h2>
      <EnvironmentTable environments={standing} />

      <h2 className="mono-label section-title">{m.detail_quotas()}</h2>
      {project.quotas.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>{m.column_metric()}</th>
              <th>{m.column_source()}</th>
              <th className="num">{m.column_usage()}</th>
            </tr>
          </thead>
          <tbody>
            {project.quotas.map((quota) => (
              <tr key={`${quota.metric}-${quota.limitSource}`}>
                <td>{metricLabel(quota)}</td>
                <td className="mute">{sourceLabel(quota)}</td>
                <td className="num">
                  <QuotaMeter quota={quota} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mute" style={{ marginTop: 14, fontSize: 15 }}>
          {m.detail_no_quotas()}
        </p>
      )}

      <h2 className="mono-label section-title">{m.detail_previews()}</h2>
      {project.previews.length > 0 ? (
        <EnvironmentTable environments={project.previews} previews />
      ) : (
        <p className="mute" style={{ marginTop: 14, fontSize: 15 }}>
          {m.detail_no_previews()}
        </p>
      )}
    </>
  );
}

function EnvironmentTable({
  environments,
  previews = false,
}: {
  environments: Environment[];
  previews?: boolean;
}) {
  return (
    <table className="table">
      <thead>
        <tr>
          <th>{m.column_environment()}</th>
          <th>{m.column_address()}</th>
          <th>{m.column_link()}</th>
          <th>{m.column_branch()}</th>
          <th>{previews ? m.column_opened() : m.column_host()}</th>
        </tr>
      </thead>
      <tbody>
        {environments.map((environment) => (
          <tr key={environment.id}>
            <td className="figures" style={{ fontSize: 13 }}>
              {environmentLabel(environment.kind)}
            </td>
            <td>
              {environment.url ? (
                <a href={environment.url} target="_blank" rel="noreferrer">
                  {hostOf(environment.url)}
                </a>
              ) : (
                <span className="mute">—</span>
              )}
              {environment.resourceStatus === "missing" ? (
                <small className="mono-label" style={{ display: "block", color: "var(--failing)" }}>
                  {m.resource_missing()}
                </small>
              ) : null}
            </td>
            <td>
              <span
                className={`link-status ${environment.linkStatus}`}
                title={environment.linkCheckedAt ? dateTime(environment.linkCheckedAt) : undefined}
              >
                {linkLabel(environment.linkStatus)}
              </span>
            </td>
            <td className="figures" style={{ fontSize: 13 }}>
              {environment.branch ?? "—"}
            </td>
            <td className="mute">
              {previews && environment.openedAt
                ? relativeTime(environment.openedAt)
                : providerLabel(environment.provider)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
