import { createFileRoute, getRouteApi } from "@tanstack/react-router";
import { Connections } from "@/features/connections/Connections";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchConnections } from "@/lib/service";

const console_ = getRouteApi("/workshop");

export const Route = createFileRoute("/workshop/connections")({
  loader: () => fetchConnections(),
  component: ConnectionsPage,
});

function ConnectionsPage() {
  const result = Route.useLoaderData();
  const { me } = console_.useLoaderData();
  if (!result.ok) return <ServiceNotice code={result.code} />;
  return <Connections connections={result.data} installUrl={me.codeHostInstallUrl} />;
}
