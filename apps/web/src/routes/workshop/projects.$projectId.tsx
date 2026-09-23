import { createFileRoute } from "@tanstack/react-router";
import { ProjectDetail } from "@/features/projects/ProjectDetail";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchProject, fetchReleases } from "@/lib/service";

export const Route = createFileRoute("/workshop/projects/$projectId")({
  loader: async ({ params }) => {
    const [project, releases] = await Promise.all([
      fetchProject({ data: params.projectId }),
      fetchReleases({ data: params.projectId }),
    ]);
    return { project, releases };
  },
  component: ProjectPage,
});

function ProjectPage() {
  const { project, releases } = Route.useLoaderData();
  if (!project.ok) return <ServiceNotice code={project.code} />;
  return <ProjectDetail project={project.data} releases={releases.ok ? releases.data : []} />;
}
