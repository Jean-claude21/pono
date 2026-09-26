import { createFileRoute } from "@tanstack/react-router";
import * as m from "@/paraglide/messages.js";
import { Consent } from "@/features/agents/Consent";
import { fetchConsent } from "@/lib/service";

type ConsentSearch = { request?: string };

// Where the authorization server sends a person when an agent asks for access (003 US1).
export const Route = createFileRoute("/oauth/consent")({
  validateSearch: (search: Record<string, unknown>): ConsentSearch => ({
    request: typeof search.request === "string" ? search.request : undefined,
  }),
  loaderDeps: ({ search }) => ({ request: search.request }),
  loader: async ({ deps }) => ({
    handle: deps.request,
    result: deps.request ? await fetchConsent({ data: deps.request }) : null,
  }),
  head: () => ({ meta: [{ title: m.consent_meta_title() }] }),
  component: ConsentPage,
});

function ConsentPage() {
  const { handle, result } = Route.useLoaderData();
  return <Consent handle={handle} result={result} />;
}
