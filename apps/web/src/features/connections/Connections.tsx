import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode, type Connection } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";
import { providerLabel } from "@/features/workshop/labels";

type KeyedProvider = { provider: string; kind: "hosting" | "database"; needsEndpoint: boolean };

// Providers without an authorization flow take a key, stored encrypted and traced (D-007).
const KEYED: KeyedProvider[] = [
  { provider: "netlify", kind: "hosting", needsEndpoint: false },
  { provider: "coolify", kind: "hosting", needsEndpoint: true },
  { provider: "neon", kind: "database", needsEndpoint: false },
];

const KIND: Record<Connection["kind"], () => string> = {
  code_host: m.kind_code_host,
  hosting: m.kind_hosting,
  database: m.kind_database,
};

const STATUS: Record<Connection["status"], [() => string, string]> = {
  active: [m.status_active, "state-healthy"],
  expired: [m.status_expired, "state-warning"],
  revoked: [m.status_revoked, "state-idle"],
};

type Props = {
  connections: Connection[];
  installUrl: string | null | undefined;
  alertEmail: string | null | undefined;
  alertEmailsEnabled: boolean;
  chatLinked: boolean;
  chatAlertsEnabled: boolean;
};

/** Connections (US1, FR-010 to FR-013): link the code host, add keys, see status, revoke. */
export function Connections({
  connections,
  installUrl,
  alertEmail,
  alertEmailsEnabled,
  chatLinked,
  chatAlertsEnabled,
}: Props) {
  const router = useRouter();
  const client = createPonoClient();
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [provider, setProvider] = useState(KEYED[0].provider);
  const chosen = KEYED.find((item) => item.provider === provider) ?? KEYED[0];
  const codeHost = connections.find(
    (connection) => connection.kind === "code_host" && connection.status === "active",
  );

  // The app is usually installed before this page is opened: link it without asking for a click.
  // The buttons stay for the case where it is not installed yet.
  const tried = useRef(false);
  useEffect(() => {
    if (codeHost || tried.current) return;
    tried.current = true;
    void client.POST("/api/v1/connections/code-host").then(({ error }) => {
      if (!error) void router.invalidate();
    });
  }, [codeHost, client, router]);

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

  function revoke(connectionId: string) {
    return run(() =>
      client.DELETE("/api/v1/connections/{connection_id}", {
        params: { path: { connection_id: connectionId } },
      }),
    );
  }

  const [addressSaved, setAddressSaved] = useState(false);

  async function saveAddress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const email = String(new FormData(event.currentTarget).get("email") ?? "").trim();
    setAddressSaved(false);
    const done = await run(() => client.PUT("/api/v1/me/email", { body: { email } }));
    setAddressSaved(done);
  }

  // Linking the chat (D-015): a one-time link, "Start" in the chat, then a confirmation here.
  const [chatUrl, setChatUrl] = useState<string | null>(null);

  async function startChat() {
    setBusy(true);
    setFailure(null);
    const { data, error } = await client.POST("/api/v1/me/chat-link");
    setBusy(false);
    if (error || !data) {
      setFailure(errorCode(error));
      return;
    }
    setChatUrl(data.url);
  }

  async function confirmChat() {
    if (await run(() => client.POST("/api/v1/me/chat-link/confirm"))) setChatUrl(null);
  }

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const endpoint = String(data.get("endpoint") ?? "").trim();
    const done = await run(() =>
      client.POST("/api/v1/connections", {
        body: {
          kind: chosen.kind,
          provider: chosen.provider,
          authorization: String(data.get("authorization") ?? ""),
          endpoint: chosen.needsEndpoint ? endpoint : null,
        },
      }),
    );
    if (done) form.reset();
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>{m.connections_title()}</h1>
          <p className="mute" style={{ marginTop: 10, fontSize: 15, maxWidth: "44em" }}>
            {m.connections_intro()}
          </p>
        </div>
      </div>

      {failure ? (
        <div className="verdict" role="alert">
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}

      <h2 className="mono-label section-title">{m.code_host_title()}</h2>
      {codeHost ? null : (
        <div style={{ marginTop: 16 }}>
          <p style={{ fontSize: 15, color: "var(--ink-soft)", maxWidth: "44em" }}>
            {m.code_host_body()}
          </p>
          <div style={{ display: "flex", gap: 10, marginTop: 14 }}>
            {installUrl ? (
              <a className="btn btn-primary btn-sm" href={installUrl} target="_blank" rel="noreferrer">
                {m.code_host_install()}
              </a>
            ) : null}
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={busy}
              onClick={() => run(() => client.POST("/api/v1/connections/code-host"))}
            >
              {m.code_host_link()}
            </button>
          </div>
        </div>
      )}

      {codeHost ? (
        <ConnectionRows
          connections={connections.filter((connection) => connection.kind === "code_host")}
          busy={busy}
          onRevoke={revoke}
        />
      ) : null}

      <h2 className="mono-label section-title">{m.providers_title()}</h2>
      <ConnectionRows
        connections={connections.filter((connection) => connection.kind !== "code_host")}
        busy={busy}
        onRevoke={revoke}
      />
      <form className="form" onSubmit={connect}>
        <div className="field">
          <label htmlFor="provider">{m.provider_label()}</label>
          <select id="provider" value={provider} onChange={(event) => setProvider(event.target.value)}>
            {KEYED.map((item) => (
              <option key={item.provider} value={item.provider}>
                {providerLabel(item.provider)} · {KIND[item.kind]()}
              </option>
            ))}
          </select>
        </div>
        {chosen.needsEndpoint ? (
          <div className="field">
            <label htmlFor="endpoint">{m.endpoint_label()}</label>
            <input id="endpoint" name="endpoint" type="url" required inputMode="url" />
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="authorization">{m.authorization_label()}</label>
          <input
            id="authorization"
            name="authorization"
            type="password"
            required
            autoComplete="off"
            spellCheck={false}
          />
          <small>{m.authorization_hint()}</small>
        </div>
        <div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
            {busy ? m.connect_running() : m.connect_action()}
          </button>
        </div>
      </form>

      <h2 className="mono-label section-title">{m.alerts_title()}</h2>
      <p style={{ marginTop: 14, fontSize: 15, color: "var(--ink-soft)", maxWidth: "44em" }}>
        {m.alerts_intro()}
      </p>

      <h3 className="alerts-channel">{m.alerts_chat_title()}</h3>
      {!chatAlertsEnabled ? (
        <p className="notice">{m.alerts_chat_off()}</p>
      ) : chatLinked ? (
        <div className="alerts-row">
          <span className="state state-healthy">{m.alerts_chat_linked()}</span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={busy}
            onClick={() => run(() => client.DELETE("/api/v1/me/chat"))}
          >
            {m.alerts_chat_unlink()}
          </button>
        </div>
      ) : chatUrl ? (
        <div>
          <p style={{ fontSize: 15, color: "var(--ink-soft)", maxWidth: "44em" }}>
            {m.alerts_chat_pending()}
          </p>
          <div className="alerts-row">
            <a className="btn btn-primary btn-sm" href={chatUrl} target="_blank" rel="noreferrer">
              {m.alerts_chat_open()}
            </a>
            <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={confirmChat}>
              {m.alerts_chat_confirm()}
            </button>
          </div>
        </div>
      ) : (
        <div className="alerts-row">
          <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={startChat}>
            {m.alerts_chat_link()}
          </button>
        </div>
      )}

      <h3 className="alerts-channel">{m.alerts_email_title()}</h3>
      <p style={{ fontSize: 15, color: "var(--ink-soft)", maxWidth: "44em" }}>{m.alerts_body()}</p>
      {alertEmailsEnabled ? null : <p className="notice">{m.alerts_mail_off()}</p>}
      <form className="form" onSubmit={saveAddress}>
        <div className="field">
          <label htmlFor="email">{m.alerts_email_label()}</label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            defaultValue={alertEmail ?? ""}
          />
          {addressSaved ? <small>{m.alerts_saved()}</small> : null}
        </div>
        <div>
          <button type="submit" className="btn btn-ghost btn-sm" disabled={busy}>
            {m.alerts_save()}
          </button>
        </div>
      </form>
    </>
  );
}

function ConnectionRows({
  connections,
  busy,
  onRevoke,
}: {
  connections: Connection[];
  busy: boolean;
  onRevoke: (connectionId: string) => void;
}) {
  if (connections.length === 0) {
    return (
      <p className="mute" style={{ marginTop: 14, fontSize: 15 }}>
        {m.no_connections()}
      </p>
    );
  }
  return (
    <table className="table" style={{ marginTop: 8 }}>
      <tbody>
        {connections.map((connection) => {
          const [label, tone] = STATUS[connection.status];
          return (
            <tr key={connection.id}>
              <td className="project">
                {providerLabel(connection.provider)}
                <small className="figures">{connection.externalRef}</small>
              </td>
              <td className="mute figures" style={{ fontSize: 13 }}>
                {KIND[connection.kind]()}
              </td>
              <td>
                <span className={`state ${tone}`}>{label()}</span>
              </td>
              <td className="mute" title={dateTime(connection.statusCheckedAt)}>
                {m.checked_when({ when: relativeTime(connection.statusCheckedAt) })}
              </td>
              <td className="num">
                {connection.status === "revoked" ? null : (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={busy}
                    onClick={() => onRevoke(connection.id)}
                  >
                    {m.revoke_action()}
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
