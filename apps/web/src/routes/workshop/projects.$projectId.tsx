import { createFileRoute } from "@tanstack/react-router";
import { ProjectDetail } from "@/features/projects/ProjectDetail";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchProject } from "@/lib/service";

export const Route = createFileRoute("/workshop/projects/$projectId")({
  loader: ({ params }) => fetchProject({ data: params.projectId }),
  component: ProjectPage,
});

function ProjectPage() {
  const result = Route.useLoaderData();
  if (!result.ok) return <ServiceNotice code={result.code} />;
  return <ProjectDetail project={result.data} />;
}
