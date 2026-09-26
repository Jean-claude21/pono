import { useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode, type Runtime, type RuntimeReport } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, integer, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";
import { FileForm } from "@/features/runtime/FileForm";

type State = Runtime["state"];

const STATE: Record<State, [() => string, string]> = {
  awaiting_files: [m.runtime_state_awaiting_files, "state-active"],
  preparing: [m.runtime_state_preparing, "state-active"],
  starting: [m.runtime_state_starting, "state-active"],
  ready: [m.runtime_state_ready, "state-healthy"],
  sleeping: [m.runtime_state_sleeping, "state-idle"],
  stopped: [m.runtime_state_stopped, "state-idle"],
  failed: [m.runtime_state_failed, "state-failing"],
  unreachable: [m.runtime_state_unreachable, "state-warning"],
};
const SERVING: State[] = ["ready", "sleeping"];
const STOPPABLE: State[] = ["awaiting_files", "preparing", "starting", "ready", "sleeping", "unreachable"];

type Props = {
  projectId: string;
  runtime: Runtime | null;
  errors: RuntimeReport[];
};

/** The project's development runtime (004): state, address, saves, errors, and every gesture. */
export function RuntimePanel({ projectId, runtime, errors }: Props) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const params = { params: { path: { project_id: projectId } } };

  async function run(action: () => Promise<{ error?: unknown }>) {
    setBusy(true);
    setFailure(null);
    const { error } = await action();
    setBusy(false);
    if (error) {
      setFailure(errorCode(error));
      return false;
    }
    await router.invalidate();
    return true;
  }

  const client = createPonoClient();
  const start = () => run(() => client.POST("/api/v1/projects/{project_id}/runtime", params));
  const stop = () => run(() => client.DELETE("/api/v1/projects/{project_id}/runtime", params));
  const save = () => run(() => client.POST("/api/v1/projects/{project_id}/runtime/save", params));

  const failureNotice = failure ? (
    <div className="verdict" role="alert" style={{ marginTop: 16 }}>
      <p>{errorMessage(failure)}</p>
    </div>
  ) : null;

  if (runtime === null) {
    return (
      <section aria-labelledby="runtime-title">
        <h2 id="runtime-title" className="mono-label section-title">
          {m.runtime_title()}
        </h2>
        <p className="mute" style={{ marginTop: 14, fontSize: 15, maxWidth: "44em" }}>
          {m.runtime_intro()}
        </p>
        {failureNotice}
        <div className="alerts-row">
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={start}>
            {m.runtime_start()}
          </button>
        </div>
      </section>
    );
  }

  const [label, tone] = STATE[runtime.state];
  const serving = SERVING.includes(runtime.state);
  const open = `/runtime/open?project=${encodeURIComponent(projectId)}`;
  const current = errors.filter((error) => !error.resolved);
  const limits = runtime.limits;

  return (
    <section aria-labelledby="runtime-title">
      <h2 id="runtime-title" className="mono-label section-title">
        {m.runtime_title()}
      </h2>
      <div className="topline" style={{ marginTop: 14 }}>
        <div className="counts mute">
          <span className={`state ${tone}`}>{label()}</span>
          {runtime.reason ? <span>{errorMessage(runtime.reason)}</span> : null}
          <span>
            {m.runtime_limits({
              started: integer(limits.started),
              max: integer(limits.maxStarted),
              minutes: integer(limits.sleepAfterMinutes),
            })}
          </span>
        </div>
        <div className="topline-actions">
          {serving ? (
            <a className="btn btn-primary btn-sm" href={open} target="_blank" rel="noreferrer">
              {m.runtime_open()}
            </a>
          ) : null}
          {runtime.pendingWrites > 0 ? (
            <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={save}>
              {m.runtime_save()}
            </button>
          ) : null}
          {STOPPABLE.includes(runtime.state) ? (
            <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={stop}>
              {m.runtime_stop()}
            </button>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={start}>
              {m.runtime_start()}
            </button>
          )}
        </div>
      </div>

      {failureNotice}
      {runtime.state === "awaiting_files" && runtime.proposalUrl ? (
        <p className="notice">
          {m.runtime_proposal({ branch: runtime.developmentBranch })}{" "}
          <a href={runtime.proposalUrl} target="_blank" rel="noreferrer">
            {m.runtime_proposal_open()}
          </a>
        </p>
      ) : null}
      {runtime.conflicts.length > 0 ? (
        <div className="notice warning">
          <p>{m.runtime_conflicts()}</p>
          <ul className="figures" style={{ margin: "8px 0 0", paddingLeft: 18, fontSize: 13 }}>
            {runtime.conflicts.map((path) => (
              <li key={path}>{path}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <dl className="facts">
        <div className="fact">
          <dt>{m.runtime_address()}</dt>
          <dd className="figures" style={{ fontSize: 13, overflowWrap: "anywhere" }}>
            {runtime.url ?? "—"}
          </dd>
        </div>
        <div className="fact">
          <dt>{m.runtime_branch()}</dt>
          <dd>
            <span className="figures" style={{ fontSize: 13 }}>
              {runtime.developmentBranch}
            </span>
            <small className="mute" style={{ display: "block" }}>
              {m.runtime_database()}
            </small>
          </dd>
        </div>
        <div className="fact">
          <dt>{m.runtime_pending()}</dt>
          <dd className="figures">{integer(runtime.pendingWrites)}</dd>
        </div>
        <div className="fact">
          <dt>{m.runtime_last_save()}</dt>
          <dd>
            {runtime.lastSave ? (
              <span title={dateTime(runtime.lastSave.savedAt)}>
                <span className="figures" style={{ fontSize: 13 }}>
                  {runtime.lastSave.commitSha.slice(0, 7)}
                </span>{" "}
                · {relativeTime(runtime.lastSave.savedAt)} · {runtime.lastSave.actor}
              </span>
            ) : (
              <span className="mute">{m.runtime_never_saved()}</span>
            )}
          </dd>
        </div>
      </dl>

      <h3 className="alerts-channel">{m.runtime_errors_title()}</h3>
      {current.length > 0 ? (
        <ul className="guards">
          {current.map((error) => (
            <li className="guard" key={`${error.source}-${error.message}-${error.file}-${error.line}`}>
              <span className="guard-name">
                {error.source === "browser" ? m.runtime_error_browser() : m.runtime_error_compile()}
              </span>
              <span className="guard-status failed">×{integer(error.count)}</span>
              <div className="guard-detail">
                <p>{error.message}</p>
                {error.file ? (
                  <ul>
                    <li>
                      {error.line
                        ? m.runtime_error_where({ file: error.file, line: String(error.line) })
                        : error.file}
                    </li>
                  </ul>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mute" style={{ fontSize: 15 }}>
          {m.runtime_no_errors()}
        </p>
      )}

      {serving ? <FileForm projectId={projectId} /> : null}
    </section>
  );
}
