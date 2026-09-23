import { createFileRoute } from "@tanstack/react-router";
import type { ProjectState } from "@pono/sdk";
import { Workshop } from "@/features/workshop/Workshop";
import { STATES } from "@/features/workshop/labels";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchWorkshop } from "@/lib/service";

type WorkshopSearch = { state?: ProjectState };

export const Route = createFileRoute("/workshop/")({
  validateSearch: (search: Record<string, unknown>): WorkshopSearch => ({
    state: STATES.includes(search.state as ProjectState) ? (search.state as ProjectState) : undefined,
  }),
  loaderDeps: ({ search }) => ({ state: search.state }),
  loader: ({ deps }) => fetchWorkshop({ data: deps.state }),
  component: WorkshopPage,
});

function WorkshopPage() {
  const result = Route.useLoaderData();
  const { state } = Route.useSearch();
  if (!result.ok) return <ServiceNotice code={result.code} />;
  return <Workshop workshop={result.data} filter={state} />;
}
