import { createFileRoute } from "@tanstack/react-router";
import { ProjectDetail } from "@/features/projects/ProjectDetail";
import { RuntimePanel } from "@/features/runtime/RuntimePanel";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchProject, fetchReleases, fetchRuntime, fetchRuntimeErrors } from "@/lib/service";

export const Route = createFileRoute("/workshop/projects/$projectId")({
  loader: async ({ params }) => {
    const [project, releases, runtime] = await Promise.all([
      fetchProject({ data: params.projectId }),
      fetchReleases({ data: params.projectId }),
      fetchRuntime({ data: params.projectId }),
    ]);
    // Errors are read live from the runtime only when it serves (004 SC-005).
    const errors =
      runtime.ok && (runtime.data.state === "ready" || runtime.data.state === "sleeping")
        ? await fetchRuntimeErrors({ data: params.projectId })
        : null;
    return { project, releases, runtime, errors };
  },
  component: ProjectPage,
});

function ProjectPage() {
  const { project, releases, runtime, errors } = Route.useLoaderData();
  if (!project.ok) return <ServiceNotice code={project.code} />;
  return (
    <>
      <ProjectDetail project={project.data} releases={releases.ok ? releases.data : []} />
      <RuntimePanel
        projectId={project.data.id}
        runtime={runtime.ok ? runtime.data : null}
        errors={errors?.ok ? errors.data.errors : []}
      />
    </>
  );
}
