import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { Agents } from "@/features/connections/Agents";
import { Connections } from "@/features/connections/Connections";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchAgents, fetchConnections } from "@/lib/service";

const console_ = getRouteApi("/workshop");

export const Route = createFileRoute("/workshop/connections")({
  loader: async () => {
    const [connections, agents] = await Promise.all([fetchConnections(), fetchAgents()]);
    return { connections, agents };
  },
  component: ConnectionsPage,
});

function ConnectionsPage() {
  const { connections, agents } = Route.useLoaderData();
  const { me } = console_.useLoaderData();
  if (!connections.ok) return <ServiceNotice code={connections.code} />;
  return (
    <>
      <Connections
        connections={connections.data}
        installUrl={me.codeHostInstallUrl}
        alertEmail={me.email}
        alertEmailsEnabled={me.alertEmailsEnabled}
        chatLinked={me.chatLinked}
        chatAlertsEnabled={me.chatAlertsEnabled}
      />
      {/* Without its key the service closes agents' access: the section is simply absent. */}
      {agents.ok ? <Agents agents={agents.data} /> : null}
    </>
  );
}
