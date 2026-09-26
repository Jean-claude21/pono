import { useState } from "react";
import { createPonoClient, errorCode, type ConsentRequest } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { dateTime, relativeTime } from "@/lib/format";
import { errorMessage } from "@/lib/i18n";
import { LocaleSwitcher } from "@/features/i18n/LocaleSwitcher";
import type { ServiceResult } from "@/lib/service";

type Access = "read" | "act";

/** An agent asks for access; only a signed-in person decides, here (003 FR-002, FR-003). */
export function Consent({
  handle,
  result,
}: {
  handle: string | undefined;
  result: ServiceResult<ConsentRequest> | null;
}) {
  return (
    <>
      <header className="site-header">
        <a className="monogram" href="/">
          <b>P</b>Pono
        </a>
        <LocaleSwitcher />
      </header>
      <main className="page">
        <p className="mono-label">{m.consent_label()}</p>
        {!handle || !result ? (
          <p className="lede">{m.consent_missing()}</p>
        ) : result.ok ? (
          <Decision handle={handle} request={result.data} />
        ) : result.status === 401 ? (
          <SignIn handle={handle} />
        ) : (
          <div className="verdict" role="alert" style={{ marginTop: 20 }}>
            <p>{errorMessage(result.code)}</p>
          </div>
        )}
        <p style={{ marginTop: 40 }}>
          <a className="mute" href="/privacy">
            {m.privacy_link()}
          </a>
        </p>
      </main>
    </>
  );
}

function SignIn({ handle }: { handle: string }) {
  const back = `/oauth/consent?request=${encodeURIComponent(handle)}`;
  return (
    <>
      <p className="lede">{m.consent_sign_in_body()}</p>
      <div className="actions">
        <a className="btn btn-primary" href={`/api/v1/auth/login?next=${encodeURIComponent(back)}`}>
          {m.sign_in()}
        </a>
      </div>
    </>
  );
}

function Decision({ handle, request }: { handle: string; request: ConsentRequest }) {
  const canAct = request.scopes.includes("pono:act");
  const [access, setAccess] = useState<Access>(canAct ? "act" : "read");
  const [busy, setBusy] = useState(false);
  const [returning, setReturning] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function decide(decision: "approve" | "deny") {
    setBusy(true);
    setFailure(null);
    const { data, error } = await createPonoClient().POST("/api/v1/oauth/consent/{decision}", {
      params: { path: { decision } },
      body: { request: handle, access: decision === "approve" ? access : null },
    });
    if (error || !data) {
      setBusy(false);
      setFailure(errorCode(error));
      return;
    }
    // Back to the agent, with a code (approved) or a refusal (denied).
    setReturning(true);
    window.location.assign(data.redirectUrl);
  }

  return (
    <>
      <h1>{m.consent_title({ client: request.clientName })}</h1>
      <p className="lede">{m.consent_organization({ name: request.organizationName })}</p>

      <fieldset className="choices" disabled={busy}>
        <legend className="mono-label" style={{ marginTop: 28, marginBottom: 10 }}>
          {m.consent_choose()}
        </legend>
        <label className="choice">
          <input
            type="radio"
            name="access"
            value="read"
            checked={access === "read"}
            onChange={() => setAccess("read")}
          />
          <strong>{m.consent_access_read()}</strong>
          <span>{m.consent_access_read_body()}</span>
        </label>
        {canAct ? (
          <label className="choice">
            <input
              type="radio"
              name="access"
              value="act"
              checked={access === "act"}
              onChange={() => setAccess("act")}
            />
            <strong>{m.consent_access_act()}</strong>
            <span>{m.consent_access_act_body()}</span>
          </label>
        ) : null}
      </fieldset>

      <p className="notice">{m.consent_never()}</p>

      {failure ? (
        <div className="verdict" role="alert" style={{ marginTop: 20 }}>
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}

      <div className="actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() => decide("approve")}
        >
          {m.consent_approve()}
        </button>
        <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => decide("deny")}>
          {m.consent_deny()}
        </button>
      </div>
      {returning ? <p className="notice">{m.consent_returning()}</p> : null}
      <p className="mute" style={{ marginTop: 16, fontSize: 13 }} title={dateTime(request.expiresAt)}>
        {m.consent_expires({ when: relativeTime(request.expiresAt) })}
      </p>
    </>
  );
}
