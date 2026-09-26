import { Link } from "@tanstack/react-router";
import type { JournalRow } from "@/lib/service";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { eventLabel, shortSha } from "@/features/releases/labels";

type Props = { projectId: string; entries: JournalRow[]; pageSize: number };

/** The evidence log of a project: append-only, newest first (002 US5, FR-018, FR-019). */
export function Journal({ projectId, entries, pageSize }: Props) {
  const oldest = entries.at(-1);
  return (
    <>
      <Link className="back" to="/workshop/projects/$projectId" params={{ projectId }}>
        ← {m.journal_back()}
      </Link>
      <div className="topline" style={{ marginTop: 12 }}>
        <div>
          <h1>{m.journal_title()}</h1>
          <p className="mute" style={{ marginTop: 10, fontSize: 15, maxWidth: "42em" }}>
            {m.journal_intro()}
          </p>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="mute" style={{ marginTop: 24, fontSize: 15 }}>
          {m.journal_empty()}
        </p>
      ) : (
        <table className="table" style={{ marginTop: 24 }}>
          <thead>
            <tr>
              <th>{m.column_when()}</th>
              <th>{m.column_event()}</th>
              <th>{m.column_actor()}</th>
              <th className="num">{m.column_version()}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td className="mute" title={dateTime(entry.occurredAt)}>
                  {relativeTime(entry.occurredAt)}
                </td>
                <td className="project">
                  {eventLabel(entry.kind)}
                  {entry.changeNumber ? (
                    <small className="figures">
                      {m.release_change({ number: String(entry.changeNumber) })}
                    </small>
                  ) : null}
                </td>
                <td className="mute">
                  {entry.actorKind === "agent"
                    ? m.actor_agent({ name: entry.actor ?? "" })
                    : (entry.actor ?? m.actor_pono())}
                </td>
                <td className="figures num" style={{ fontSize: 13 }}>
                  {shortSha(entry.headSha)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {oldest && entries.length >= pageSize ? (
        <div style={{ marginTop: 16 }}>
          <Link
            className="btn btn-ghost btn-sm"
            to="/workshop/projects/$projectId/journal"
            params={{ projectId }}
            search={{ before: oldest.id }}
          >
            {m.journal_older()}
          </Link>
        </div>
      ) : null}
    </>
  );
}
