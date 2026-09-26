import { useEffect, useState } from "react";
import { useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode, type AgentGrant } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";

const ACCESS: Record<AgentGrant["access"], () => string> = {
  read: m.agents_access_read,
  act: m.agents_access_act,
};

/** Agents linked to the workshop (003 US4, FR-005): who, what access, since when; cut at once. */
export function Agents({ agents }: { agents: AgentGrant[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  // The tools server lives at the console's own address (003 FR-001).
  const [address, setAddress] = useState("");
  useEffect(() => setAddress(`${window.location.origin}/mcp`), []);

  async function revoke(grantId: string) {
    setBusy(true);
    setFailure(null);
    const { error } = await createPonoClient().DELETE("/api/v1/agents/{grant_id}", {
      params: { path: { grant_id: grantId } },
    });
    setBusy(false);
    if (error) {
      setFailure(errorCode(error));
      return;
    }
    await router.invalidate();
  }

  return (
    <>
      <h2 className="mono-label section-title">{m.agents_title()}</h2>
      <p style={{ marginTop: 14, fontSize: 15, color: "var(--ink-soft)", maxWidth: "44em" }}>
        {m.agents_intro()}
      </p>
      <div className="field" style={{ marginTop: 14, maxWidth: 520 }}>
        <label htmlFor="agents-address">{m.agents_address()}</label>
        <output id="agents-address" className="address">
          {address}
        </output>
      </div>

      {failure ? (
        <div className="verdict" role="alert" style={{ marginTop: 20 }}>
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}

      {agents.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>{m.agents_column_client()}</th>
              <th>{m.agents_column_access()}</th>
              <th>{m.agents_column_granted()}</th>
              <th>{m.agents_column_last_used()}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr key={agent.id}>
                <td className="project">{agent.clientName}</td>
                <td>{ACCESS[agent.access]()}</td>
                <td className="mute" title={dateTime(agent.grantedAt)}>
                  {relativeTime(agent.grantedAt)}
                </td>
                <td className="mute" title={agent.lastUsedAt ? dateTime(agent.lastUsedAt) : undefined}>
                  {agent.lastUsedAt ? relativeTime(agent.lastUsedAt) : m.agents_never_used()}
                </td>
                <td className="num">
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy}
                    onClick={() => revoke(agent.id)}
                  >
                    {m.agents_revoke()}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="mute" style={{ marginTop: 14, fontSize: 15 }}>
          {m.agents_empty()}
        </p>
      )}
    </>
  );
}
