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

// The chat linking flow keeps its state here: link, confirm, unlink.
let chatLinked = false;

// Guarded release (002) on lectio: one refused change, one waiting for approval.
const HEAD = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678";
const guard = (name, status, reason, findings = []) => ({
  guard: name,
  status,
  reason,
  findings,
  checkedAt: hoursAgo(0.05),
});
const releaseState = { approved: false, protected: false, rolledBack: false };

function releases() {
  return [
    {
      id: "01990000-0000-7000-8000-00000000r001",
      changeNumber: 12,
      changeUrl: "https://code-host.example.test/alice/lectio/pull/12",
      title: "Drop the notes body",
      author: "coding-agent[bot]",
      headSha: "ffee0011223344556677889900aabbccddeeff00",
      headBranch: "feature/drop",
      verdict: "refused",
      state: "open",
      openedAt: hoursAgo(1),
      evaluatedAt: hoursAgo(0.9),
      approvedBy: null,
      approvedAt: null,
      guards: [
        guard("secrets", "passed", null),
        guard("migrations", "failed", "migrations.destructive", [
          {
            code: "migrations.destructive",
            file: "drizzle/0003_drop_notes.sql",
            line: 2,
            operation: "drop_column",
            url: null,
          },
        ]),
        guard("preview", "passed", "preview.ready"),
      ],
    },
    {
      id: "01990000-0000-7000-8000-00000000r002",
      changeNumber: 13,
      changeUrl: "https://code-host.example.test/alice/lectio/pull/13",
      title: "Add tags",
      author: "coding-agent[bot]",
      headSha: HEAD,
      headBranch: "feature/tags",
      verdict: releaseState.approved ? "approved" : "awaiting_approval",
      state: "open",
      openedAt: hoursAgo(0.5),
      evaluatedAt: hoursAgo(0.4),
      approvedBy: releaseState.approved ? "alice" : null,
      approvedAt: releaseState.approved ? hoursAgo(0) : null,
      guards: [
        guard("secrets", "passed", null),
        guard("migrations", "passed", null),
        guard("preview", "passed", "preview.ready"),
      ],
    },
  ];
}

const JOURNAL = [
  ["release.awaiting_approval", "pono", null, 13],
  ["release.refused", "pono", null, 12],
  ["release.opened", "agent", "coding-agent[bot]", 12],
  ["protection.missing", "pono", null, null],
].map(([kind, actorKind, actor, changeNumber], index) => ({
  id: `01990000-0000-7000-8000-0000000j000${index}`,
  kind,
  actorKind,
  actor,
  headSha: changeNumber ? HEAD : null,
  changeNumber,
  occurredAt: hoursAgo(index * 0.2),
  detail: {},
}));

// Agents (003): one consent request, the linked agents, and vestio's pending rollback request.
const CONSENT = "consent-handle-0123456789";
let agents = [
  {
    id: "01990000-0000-7000-8000-00000000g001",
    clientName: "Claude",
    access: "act",
    grantedAt: hoursAgo(48),
    lastUsedAt: hoursAgo(0.3),
  },
  {
    id: "01990000-0000-7000-8000-00000000g002",
    clientName: "Codex",
    access: "read",
    grantedAt: hoursAgo(2),
    lastUsedAt: null,
  },
];
let rollbackRequest = {
  id: "01990000-0000-7000-8000-00000000q001",
  clientName: "Claude",
  requestedAt: hoursAgo(0.2),
};
const VESTIO = HEALTHY[1].id;

async function bodyOf(request) {
  let raw = "";
  for await (const chunk of request) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

function scenarioOf(request) {
  const match = /pono_session=(\w+)/.exec(request.headers.cookie ?? "");
  return match && match[1] in SCENARIOS ? match[1] : null;
}

function send(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(body === undefined ? "" : JSON.stringify(body));
}

createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://localhost:${PORT}`);
  if (url.pathname === "/api/v1/health") return send(response, 200, { status: "ok" });
  // Agents' protocol paths (003): the console must pass them through untouched.
  if (url.pathname === "/.well-known/oauth-authorization-server" || url.pathname === "/mcp") {
    return send(response, 200, { relayed: url.pathname, method: request.method });
  }
  const scenario = scenarioOf(request);
  if (!scenario) return send(response, 401, { error: { code: "auth.session_required" } });
  if (url.pathname === "/api/v1/me/locale" && request.method === "PUT") {
    response.writeHead(204);
    return response.end();
  }
  if (url.pathname === "/api/v1/me/chat-link" && request.method === "POST") {
    return send(response, 200, {
      url: "https://chat.example.test/pono_bot?start=one-time-code",
      expiresAt: new Date(Date.now() + 15 * 60_000).toISOString(),
    });
  }
  if (url.pathname === "/api/v1/me/chat-link/confirm" && request.method === "POST") {
    chatLinked = true;
    response.writeHead(204);
    return response.end();
  }
  if (url.pathname === "/api/v1/me/chat" && request.method === "DELETE") {
    chatLinked = false;
    response.writeHead(204);
    return response.end();
  }
  if (url.pathname === "/api/v1/me") {
    return send(response, 200, {
      personId: "01990000-0000-7000-8000-00000000aaaa",
      login: "alice",
      organizationId: "01990000-0000-7000-8000-00000000bbbb",
      locale: null,
      email: null,
      alertEmailsEnabled: false,
      codeHostInstallUrl: "https://code-host.example.test/install",
      chatLinked,
      chatAlertsEnabled: true,
    });
  }
  if (url.pathname === "/api/v1/oauth/consent") {
    if (url.searchParams.get("request") !== CONSENT) {
      return send(response, 404, { error: { code: "oauth.request_not_found" } });
    }
    return send(response, 200, {
      clientName: "Claude",
      scopes: ["pono:read", "pono:act"],
      organizationName: "alice",
      expiresAt: new Date(Date.now() + 10 * 60_000).toISOString(),
    });
  }
  const decided = /^\/api\/v1\/oauth\/consent\/(approve|deny)$/.exec(url.pathname);
  if (decided && request.method === "POST") {
    const { access } = await bodyOf(request);
    // Back to "the agent": here, a console page the test can recognize.
    return send(response, 200, { redirectUrl: `/privacy?decision=${decided[1]}&access=${access}` });
  }
  if (url.pathname === "/api/v1/agents") return send(response, 200, agents);
  const cut = /^\/api\/v1\/agents\/([\w-]+)$/.exec(url.pathname);
  if (cut && request.method === "DELETE") {
    agents = agents.filter((agent) => agent.id !== cut[1]);
    response.writeHead(204);
    return response.end();
  }
  const asked = /^\/api\/v1\/projects\/([\w-]+)\/rollback-requests\/([\w-]+)\/(confirm|dismiss)$/.exec(
    url.pathname,
  );
  // Confirmed or dismissed, the request is gone; the answer is the project detail.
  if (asked && request.method === "POST") rollbackRequest = null;
  if (url.pathname === "/api/v1/projects") {
    return send(response, 200, workshop(scenario, url.searchParams.get("state")));
  }
  const detail = asked ?? /^\/api\/v1\/projects\/([\w-]+)$/.exec(url.pathname);
  if (detail) {
    const found = SCENARIOS[scenario].find((item) => item.id === detail[1]);
    if (!found) return send(response, 404, { error: { code: "project.not_found" } });
    return send(response, 200, {
      ...found,
      manifestProposalUrl: null,
      previews: [],
      quotas: found.quota ? [found.quota] : [],
      protection: {
        status: releaseState.protected ? "protected" : "unprotected",
        branch: "main",
        checkedAt: hoursAgo(0.1),
      },
      canRollback: true,
      rollbackRequest: found.id === VESTIO ? rollbackRequest : null,
    });
  }
  const guarded = /^\/api\/v1\/projects\/([\w-]+)\/(releases|journal|protection|rollback)(?:\/([\w-]+)\/(approval|evaluation))?$/.exec(
    url.pathname,
  );
  if (guarded) {
    const [, , what, , action] = guarded;
    if (what === "releases" && !action) return send(response, 200, releases());
    if (action === "approval") {
      releaseState.approved = true;
      return send(response, 200, releases()[1]);
    }
    if (action === "evaluation") {
      response.writeHead(202);
      return response.end();
    }
    if (what === "journal") return send(response, 200, JOURNAL);
    if (what === "protection") {
      releaseState.protected = true;
      return send(response, 200, { status: "protected", branch: "main", checkedAt: hoursAgo(0) });
    }
    if (what === "rollback") {
      releaseState.rolledBack = true;
      return send(response, 202, {
        id: "01990000-0000-7000-8000-00000000b001",
        status: "queued",
        toCommit: "old0001",
        requestedAt: hoursAgo(0),
      });
    }
  }
  if (url.pathname === "/api/v1/connections") return send(response, 200, []);
  if (url.pathname === "/api/v1/repositories") {
    return send(response, 422, { error: { code: "connection.code_host_missing" } });
  }
  return send(response, 404, { error: { code: "request.invalid" } });
}).listen(PORT, () => console.log(`mock service on ${PORT}`));
