import { createFileRoute, Link, Outlet, redirect, useRouter } from "@tanstack/react-router";
import { createPonoClient } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { integer } from "@/lib/format";
import { fetchConnections, fetchMe, fetchWorkshop } from "@/lib/service";

export const Route = createFileRoute("/workshop")({
  loader: async () => {
    const [me, workshop, connections] = await Promise.all([
      fetchMe(),
      fetchWorkshop({ data: undefined }),
      fetchConnections(),
    ]);
    if (!me.ok) {
      throw redirect({ to: "/", search: { error: me.status === 401 ? "auth.session_required" : me.code } });
    }
    return {
      me: me.data,
      projectCount: workshop.ok ? workshop.data.projects.length : 0,
      connectionCount: connections.ok ? connections.data.length : 0,
    };
  },
  head: () => ({ meta: [{ title: m.console_meta_title() }] }),
  component: ConsoleLayout,
});

function ConsoleLayout() {
  const { me, projectCount, connectionCount } = Route.useLoaderData();
  const router = useRouter();

  async function signOut() {
    await createPonoClient().POST("/api/v1/auth/logout");
    await router.navigate({ to: "/" });
  }

  return (
    <div className="console">
      <aside className="rail">
        <Link className="monogram" to="/">
          <b>P</b>Pono
        </Link>

        <div>
          <p className="mono-label" style={{ padding: "0 10px 8px" }}>
            {m.rail_workshop()}
          </p>
          <nav>
            <Link to="/workshop" activeOptions={{ exact: true, includeSearch: false }} activeProps={{ "aria-current": "page" }}>
              {m.rail_projects()} <span className="figures">{integer(projectCount)}</span>
            </Link>
            <Link to="/workshop/import" activeProps={{ "aria-current": "page" }}>
              {m.rail_import()}
            </Link>
          </nav>
        </div>

        <div>
          <p className="mono-label" style={{ padding: "0 10px 8px" }}>
            {m.rail_organization()}
          </p>
          <nav>
            <Link to="/workshop/connections" activeProps={{ "aria-current": "page" }}>
              {m.rail_connections()} <span className="figures">{integer(connectionCount)}</span>
            </Link>
          </nav>
        </div>

        <div className="foot">
          <span className="mono-label" style={{ padding: "0 10px" }}>
            {me.login}
          </span>
          <span className="mute" style={{ fontSize: 13, padding: "0 10px" }}>
            {m.rail_personal_workshop()}
          </span>
          <button
            type="button"
            className="mute"
            style={{ fontSize: 13, padding: "4px 10px", textAlign: "left" }}
            onClick={signOut}
          >
            {m.sign_out()}
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
