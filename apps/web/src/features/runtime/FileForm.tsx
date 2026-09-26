import { useState, type ChangeEvent, type FormEvent } from "react";
import { useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { errorMessage } from "@/lib/i18n";

/**
 * The console's way to write a file into the runtime, as an agent does (principle VIII,
 * clarification of 004 US2). Not an editor: a path and a content, typed or dropped.
 */
export function FileForm({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [dropped, setDropped] = useState<string | null>(null);
  const client = createPonoClient();
  const path = { params: { path: { project_id: projectId } } };

  async function settle(result: { error?: unknown }, message: string) {
    setBusy(false);
    if (result.error) {
      setFailure(errorCode(result.error));
      setDone(null);
      return;
    }
    setFailure(null);
    setDone(message);
    await router.invalidate();
  }

  function drop(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      setDropped(null);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const url = String(reader.result ?? "");
      setDropped(url.slice(url.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  }

  async function write(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const target = String(data.get("path") ?? "").trim();
    setBusy(true);
    const body = dropped
      ? { path: target, contentBase64: dropped }
      : { path: target, content: String(data.get("content") ?? "") };
    const result = await client.PUT("/api/v1/projects/{project_id}/runtime/files", {
      ...path,
      body,
    });
    await settle(result, m.runtime_file_written({ path: target }));
  }

  async function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = String(new FormData(event.currentTarget).get("delete") ?? "").trim();
    setBusy(true);
    const result = await client.DELETE("/api/v1/projects/{project_id}/runtime/files", {
      params: { path: { project_id: projectId }, query: { path: target } },
    });
    await settle(result, m.runtime_file_deleted({ path: target }));
  }

  return (
    <>
      <h3 className="alerts-channel">{m.runtime_file_title()}</h3>
      <p className="mute" style={{ fontSize: 14, maxWidth: "44em" }}>
        {m.runtime_file_intro()}
      </p>
      {failure ? (
        <div className="verdict" role="alert" style={{ marginTop: 12 }}>
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}
      {done ? (
        <p className="notice" role="status">
          {done}
        </p>
      ) : null}
      <form className="form" onSubmit={write}>
        <div className="field">
          <label htmlFor="runtime-path">{m.runtime_file_path()}</label>
          <input id="runtime-path" name="path" required spellCheck={false} />
        </div>
        <div className="field">
          <label htmlFor="runtime-content">{m.runtime_file_content()}</label>
          <textarea
            id="runtime-content"
            name="content"
            rows={8}
            spellCheck={false}
            disabled={dropped !== null}
            className="figures"
          />
        </div>
        <div className="field">
          <label htmlFor="runtime-drop">{m.runtime_file_drop()}</label>
          <input id="runtime-drop" type="file" onChange={drop} />
        </div>
        <div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
            {m.runtime_file_write()}
          </button>
        </div>
      </form>
      <form className="form" onSubmit={remove}>
        <div className="field">
          <label htmlFor="runtime-delete">{m.runtime_file_delete_path()}</label>
          <input id="runtime-delete" name="delete" required spellCheck={false} />
        </div>
        <div>
          <button type="submit" className="btn btn-ghost btn-sm" disabled={busy}>
            {m.runtime_file_delete()}
          </button>
        </div>
      </form>
    </>
  );
}
