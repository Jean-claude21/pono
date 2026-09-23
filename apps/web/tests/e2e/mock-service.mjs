// A stand-in for the Pono service during end-to-end tests. The session cookie names the scenario:
// `empty`, `healthy` or `failing`. No cookie means nobody is signed in.
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_PORT ?? 8123);
const hoursAgo = (hours) => new Date(Date.now() - hours * 3600_000).toISOString();

const environment = (id, kind, url, linkStatus) => ({
  id,
  kind,
  branch: kind === "production" ? "main" : "dev",
  url,
  provider: kind === "production" ? "netlify" : "coolify",
  resourceStatus: "found",
  linkStatus,
  linkCheckedAt: hoursAgo(0.1),
  openedAt: null,
});

const project = (id, name, state, stateReason, productionLink, quotaRatio) => ({
  id,
  repository: `alice/${name}`,
  name,
  state,
  stateReason,
  manifestStatus: "present",
  databaseStatus: "found",
  environments: [
    environment(`${id.slice(0, -4)}e001`, "production", `https://${name}.example.test`, productionLink),
    environment(`${id.slice(0, -4)}e002`, "development", `https://dev.${name}.example.test`, "up"),
  ],
  lastDeployment: {
    environmentKind: "production",
    status: state === "failing" ? "failed" : "succeeded",
    commitSha: "abc123",
    author: "alice",
    startedAt: hoursAgo(30),
    finishedAt: hoursAgo(29.9),
  },
  quota:
    quotaRatio === null
      ? null
      : {
          metric: "db_storage_bytes",
          used: 536870912 * quotaRatio,
          limit: 536870912,
          limitSource: "account_plan",
          ratio: quotaRatio,
          readAt: hoursAgo(0.5),
        },
  lastActivityAt: hoursAgo(30),
  refreshedAt: hoursAgo(0.1),
  stale: false,
});

const HEALTHY = [
  project("01990000-0000-7000-8000-000000000001", "lectio", "healthy", "nominal", "up", 0.06),
  project("01990000-0000-7000-8000-000000000002", "vestio", "healthy", "nominal", "up", 0.4),
  project("01990000-0000-7000-8000-000000000003", "nettio", "idle", "no_recent_activity", "up", null),
];
const FAILING = [
  project("01990000-0000-7000-8000-000000000004", "nyatefe", "failing", "production_down", "down", 0.97),
  project("01990000-0000-7000-8000-000000000005", "boutiqflow", "warning", "quota_warning", "up", 0.88),
  ...HEALTHY.slice(0, 1),
];
const SCENARIOS = { empty: [], healthy: HEALTHY, failing: FAILING };
const VERDICTS = {
  empty: [],
  healthy: [],
  failing: [
    { projectId: FAILING[0].id, code: "project.production_down" },
    { projectId: FAILING[0].id, code: "project.quota_critical" },
    { projectId: FAILING[1].id, code: "project.quota_warning" },
  ],
};

function workshop(scenario, state) {
  const projects = SCENARIOS[scenario];
  const counts = { healthy: 0, active: 0, warning: 0, failing: 0, idle: 0 };
  for (const item of projects) counts[item.state] += 1;
  return {
    projects: projects.filter((item) => !state || item.state === state),
    counts,
    verdicts: VERDICTS[scenario],
  };
}

function scenarioOf(request) {
  const match = /pono_session=(\w+)/.exec(request.headers.cookie ?? "");
  return match && match[1] in SCENARIOS ? match[1] : null;
}

function send(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(body === undefined ? "" : JSON.stringify(body));
}

createServer((request, response) => {
  const url = new URL(request.url ?? "/", `http://localhost:${PORT}`);
  if (url.pathname === "/api/v1/health") return send(response, 200, { status: "ok" });
  const scenario = scenarioOf(request);
  if (!scenario) return send(response, 401, { error: { code: "auth.session_required" } });
  if (url.pathname === "/api/v1/me/locale" && request.method === "PUT") {
    response.writeHead(204);
    return response.end();
  }
  if (url.pathname === "/api/v1/me") {
    return send(response, 200, {
      personId: "01990000-0000-7000-8000-00000000aaaa",
      login: "alice",
      organizationId: "01990000-0000-7000-8000-00000000bbbb",
      locale: null,
      codeHostInstallUrl: "https://code-host.example.test/install",
    });
  }
  if (url.pathname === "/api/v1/projects") {
    return send(response, 200, workshop(scenario, url.searchParams.get("state")));
  }
  const detail = /^\/api\/v1\/projects\/([\w-]+)$/.exec(url.pathname);
  if (detail) {
    const found = SCENARIOS[scenario].find((item) => item.id === detail[1]);
    if (!found) return send(response, 404, { error: { code: "project.not_found" } });
    return send(response, 200, {
      ...found,
      manifestProposalUrl: null,
      previews: [],
      quotas: found.quota ? [found.quota] : [],
    });
  }
  if (url.pathname === "/api/v1/connections") return send(response, 200, []);
  if (url.pathname === "/api/v1/repositories") {
    return send(response, 422, { error: { code: "connection.code_host_missing" } });
  }
  return send(response, 404, { error: { code: "request.invalid" } });
}).listen(PORT, () => console.log(`mock service on ${PORT}`));
