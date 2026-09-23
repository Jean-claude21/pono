import { createServerFn } from "@tanstack/react-start";
import { getRequestHeader } from "@tanstack/react-start/server";
import type { Connection, Me, ProjectDetail, Repository, Workshop } from "@pono/sdk";

// Reads run on the console's server: it calls the internal service with the visitor's cookie,
// so the first render already holds the data and the service is never exposed (research R-04).
// Writes go from the browser through the same-origin relay (`/api/*`) with the typed SDK.

export type ServiceResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; code: string };

function serviceUrl(): string {
  return (process.env.PONO_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

async function read<T>(path: string): Promise<ServiceResult<T>> {
  const cookie = getRequestHeader("cookie");
  try {
    const response = await fetch(`${serviceUrl()}/api/v1${path}`, {
      headers: { accept: "application/json", ...(cookie ? { cookie } : {}) },
    });
    const body: unknown = await response.json().catch(() => null);
    if (response.ok) return { ok: true, data: body as T };
    const code =
      (body as { error?: { code?: string } } | null)?.error?.code ?? `http.${response.status}`;
    return { ok: false, status: response.status, code };
  } catch {
    return { ok: false, status: 503, code: "service.unreachable" };
  }
}

export const fetchMe = createServerFn({ method: "GET" }).handler(() => read<Me>("/me"));

export const fetchWorkshop = createServerFn({ method: "GET" })
  .validator((state: string | undefined) => state)
  .handler(({ data: state }) =>
    read<Workshop>(state ? `/projects?state=${encodeURIComponent(state)}` : "/projects"),
  );

export const fetchProject = createServerFn({ method: "GET" })
  .validator((projectId: string) => projectId)
  .handler(({ data: projectId }) =>
    read<ProjectDetail>(`/projects/${encodeURIComponent(projectId)}`),
  );

export const fetchConnections = createServerFn({ method: "GET" }).handler(() =>
  read<Connection[]>("/connections"),
);

export const fetchRepositories = createServerFn({ method: "GET" }).handler(() =>
  read<Repository[]>("/repositories"),
);
