import { createFileRoute, redirect } from "@tanstack/react-router";
import * as m from "@/paraglide/messages.js";
import { errorMessage } from "@/lib/i18n";
import { fetchRuntimeTicket } from "@/lib/service";

type OpenSearch = { project?: string; return?: string };

// Where a runtime's gate sends a visitor without a session (004 research R-04): a signed-in member
// of the project's organization gets a one-time ticket and goes on to the runtime; anyone else is
// sent to sign in, then comes back here.
export const Route = createFileRoute("/runtime/open")({
  validateSearch: (search: Record<string, unknown>): OpenSearch => ({
    project: typeof search.project === "string" ? search.project : undefined,
    return: typeof search.return === "string" ? search.return : undefined,
  }),
  loaderDeps: ({ search }) => ({ project: search.project, back: search.return }),
  loader: async ({ deps }) => {
    if (!deps.project) return { code: "runtime.not_found" };
    const back = deps.back?.startsWith("/") ? deps.back : "/";
    const ticket = await fetchRuntimeTicket({ data: { projectId: deps.project, returnPath: back } });
    if (ticket.ok) throw redirect({ href: ticket.data.url });
    if (ticket.status === 401) {
      const here = `/runtime/open?${new URLSearchParams({ project: deps.project, return: back })}`;
      throw redirect({ href: `/api/v1/auth/login?next=${encodeURIComponent(here)}` });
    }
    return { code: ticket.code };
  },
  head: () => ({ meta: [{ title: m.runtime_open_meta_title() }] }),
  component: OpenRuntime,
});

function OpenRuntime() {
  const { code } = Route.useLoaderData();
  return (
    <main className="page">
      <p className="mono-label">{m.runtime_title()}</p>
      <div className="verdict" role="alert" style={{ marginTop: 20 }}>
        <p>{errorMessage(code)}</p>
      </div>
      <p style={{ marginTop: 24 }}>
        <a className="btn btn-ghost btn-sm" href="/workshop">
          {m.detail_back()}
        </a>
      </p>
    </main>
  );
}
