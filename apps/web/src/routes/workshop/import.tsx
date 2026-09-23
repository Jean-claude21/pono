import { createFileRoute } from "@tanstack/react-router";
import { CodeHostMissing, ImportProject } from "@/features/projects/ImportProject";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchRepositories } from "@/lib/service";

export const Route = createFileRoute("/workshop/import")({
  loader: () => fetchRepositories(),
  component: ImportPage,
});

function ImportPage() {
  const result = Route.useLoaderData();
  if (!result.ok) {
    if (result.code === "connection.code_host_missing") return <CodeHostMissing />;
    return <ServiceNotice code={result.code} />;
  }
  return <ImportProject repositories={result.data} />;
}
