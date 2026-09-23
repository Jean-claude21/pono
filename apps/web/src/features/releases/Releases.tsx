import { useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode, type GuardResult, type Release } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";
import {
  guardName,
  guardReason,
  guardStatusLabel,
  operationLabel,
  releaseStateLabel,
  shortSha,
  verdictTone,
} from "@/features/releases/labels";

type Props = { projectId: string; releases: Release[] };

/** Every change towards production, its guards, and the one gesture that lets it ship (002). */
export function Releases({ projectId, releases }: Props) {
  const open = releases.filter((release) => release.state === "open");
  const closed = releases.filter((release) => release.state !== "open").slice(0, 5);
  return (
    <>
      <h2 className="mono-label section-title">{m.releases_title()}</h2>
      {open.length === 0 ? (
        <p className="mute" style={{ marginTop: 14, fontSize: 15 }}>
          {m.releases_empty()}
        </p>
      ) : (
        open.map((release) => (
          <ReleaseCard key={release.id} projectId={projectId} release={release} />
        ))
      )}
      {closed.length > 0 ? (
        <table className="table releases-closed">
          <caption className="mono-label">{m.release_closed_title()}</caption>
          <tbody>
            {closed.map((release) => (
              <tr key={release.id}>
                <td className="project">
                  <a href={release.changeUrl} target="_blank" rel="noreferrer">
                    {m.release_change({ number: String(release.changeNumber) })}
                  </a>
                  <small>{release.title}</small>
                </td>
                <td className="mute">{releaseStateLabel(release)}</td>
                <td className="figures num" style={{ fontSize: 13 }}>
                  {shortSha(release.headSha)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </>
  );
}

function ReleaseCard({ projectId, release }: { projectId: string; release: Release }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [queued, setQueued] = useState(false);
  const client = createPonoClient();
  const path = { project_id: projectId, release_id: release.id };
  const tone = verdictTone(release.verdict);

  async function approve() {
    setBusy(true);
    setFailure(null);
    const { error } = await client.POST(
      "/api/v1/projects/{project_id}/releases/{release_id}/approval",
      { params: { path }, body: { headSha: release.headSha } },
    );
    setBusy(false);
    if (error) {
      setFailure(errorCode(error));
      return;
    }
    await router.invalidate();
  }

  async function evaluate() {
    setQueued(true);
    await client.POST("/api/v1/projects/{project_id}/releases/{release_id}/evaluation", {
      params: { path },
    });
    window.setTimeout(() => {
      setQueued(false);
      void router.invalidate();
    }, 4000);
  }

  return (
    <article className={`release release-${tone}`} aria-label={releaseStateLabel(release)}>
      <header className="release-head">
        <div>
          <span className="mono-label">{releaseStateLabel(release)}</span>
          <h3>
            <a href={release.changeUrl} target="_blank" rel="noreferrer">
              {m.release_change({ number: String(release.changeNumber) })}
            </a>{" "}
            · {release.title}
          </h3>
          <p className="mute" title={dateTime(release.openedAt)}>
            {m.release_meta({ author: release.author, sha: shortSha(release.headSha) })}
          </p>
        </div>
        <div className="release-actions">
          {release.verdict === "awaiting_approval" ? (
            <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={approve}>
              {busy ? m.release_approving() : m.release_approve({ sha: shortSha(release.headSha) })}
            </button>
          ) : null}
          {release.verdict === "refused" || release.verdict === "evaluating" ? (
            <button type="button" className="btn btn-ghost btn-sm" disabled={queued} onClick={evaluate}>
              {m.release_evaluate()}
            </button>
          ) : null}
        </div>
      </header>

      {queued ? <p className="notice">{m.release_evaluate_queued()}</p> : null}
      {failure ? (
        <p className="notice warning" role="alert">
          {errorMessage(failure)}
        </p>
      ) : null}
      {release.approvedBy && release.approvedAt ? (
        <p className="mute" style={{ marginTop: 10, fontSize: 14 }}>
          {m.release_approved_by({ login: release.approvedBy, when: relativeTime(release.approvedAt) })}
        </p>
      ) : null}

      <ul className="guards">
        {release.guards.map((guard) => (
          <GuardRow key={guard.guard} guard={guard} />
        ))}
      </ul>
    </article>
  );
}

function GuardRow({ guard }: { guard: GuardResult }) {
  const findings = guard.findings.filter((finding) => finding.file || finding.url);
  return (
    <li className={`guard guard-${guard.status}`}>
      <span className="guard-name">{guardName(guard.guard)}</span>
      <span className={`guard-status ${guard.status}`}>{guardStatusLabel(guard.status)}</span>
      <div className="guard-detail">
        {guard.reason ? <p>{guardReason(guard.reason)}</p> : null}
        {findings.length > 0 ? (
          <ul>
            {findings.map((finding, index) => (
              <li key={`${finding.file ?? finding.url}-${index}`} className="figures">
                {finding.file ?? finding.url}
                {finding.line ? ` · ${m.release_finding_line({ line: String(finding.line) })}` : null}
                {finding.operation ? ` · ${operationLabel(finding.operation)}` : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </li>
  );
}
