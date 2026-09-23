import { createFileRoute } from "@tanstack/react-router";
import { Journal } from "@/features/releases/Journal";
import { ServiceNotice } from "@/features/workshop/ServiceNotice";
import { fetchJournal } from "@/lib/service";

const PAGE_SIZE = 50;

type JournalSearch = { before?: string };

export const Route = createFileRoute("/workshop/projects/$projectId_/journal")({
  validateSearch: (search: Record<string, unknown>): JournalSearch => ({
    before: typeof search.before === "string" ? search.before : undefined,
  }),
  loaderDeps: ({ search }) => ({ before: search.before }),
  loader: ({ params, deps }) =>
    fetchJournal({ data: { projectId: params.projectId, before: deps.before } }),
  component: JournalPage,
});

function JournalPage() {
  const result = Route.useLoaderData();
  const { projectId } = Route.useParams();
  if (!result.ok) return <ServiceNotice code={result.code} />;
  return <Journal projectId={projectId} entries={result.data} pageSize={PAGE_SIZE} />;
}
