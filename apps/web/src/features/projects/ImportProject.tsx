import { useState } from "react";
import { Link, useRouter } from "@tanstack/react-router";
import { createPonoClient, errorCode, type Repository } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { errorMessage } from "@/lib/i18n";

type Props = { repositories: Repository[] };

/** Import (US1): pick a repository, nothing to type. The service reads or proposes the manifest. */
export function ImportProject({ repositories }: Props) {
  const router = useRouter();
  const [running, setRunning] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  async function importRepository(fullName: string) {
    setRunning(fullName);
    setFailure(null);
    const { data, error } = await createPonoClient().POST("/api/v1/projects", {
      body: { repository: fullName },
    });
    setRunning(null);
    if (error || !data) {
      setFailure(errorCode(error));
      return;
    }
    await router.navigate({ to: "/workshop/projects/$projectId", params: { projectId: data.id } });
  }

  return (
    <>
      <div className="topline">
        <div>
          <h1>{m.import_title()}</h1>
          <p className="mute" style={{ marginTop: 10, fontSize: 15, maxWidth: "42em" }}>
            {m.import_intro()}
          </p>
        </div>
      </div>

      {failure ? (
        <div className="verdict" role="alert">
          <p>{errorMessage(failure)}</p>
        </div>
      ) : null}

      {repositories.length === 0 ? (
        <p className="notice">{m.import_empty()}</p>
      ) : (
        <table className="table" style={{ marginTop: 24 }}>
          <tbody>
            {repositories.map((repository) => (
              <tr key={repository.fullName}>
                <td className="project">
                  {repository.fullName}
                  <small className="figures">{repository.defaultBranch}</small>
                </td>
                <td className="num">
                  {repository.alreadyImported && repository.projectId ? (
                    <Link
                      className="btn btn-ghost btn-sm"
                      to="/workshop/projects/$projectId"
                      params={{ projectId: repository.projectId }}
                    >
                      {m.import_open()}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      disabled={running !== null}
                      onClick={() => importRepository(repository.fullName)}
                    >
                      {running === repository.fullName ? m.import_running() : m.import_action()}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

export function CodeHostMissing() {
  return (
    <>
      <div className="topline">
        <h1>{m.import_title()}</h1>
      </div>
      <div className="verdict healthy">
        <div>
          <h3>{m.import_code_host_missing()}</h3>
        </div>
        <Link className="btn btn-primary btn-sm" style={{ flexShrink: 0 }} to="/workshop/connections">
          {m.import_go_connections()}
        </Link>
      </div>
    </>
  );
}
