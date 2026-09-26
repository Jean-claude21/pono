// Same-origin relay to the Pono service (research R-04). The browser only ever talks to the
// console's origin: the session cookie stays first-party and the service is never exposed.
const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "transfer-encoding",
  "upgrade",
  "host",
  // fetch already decoded the body: forwarding these would make the browser decode it twice.
  "content-encoding",
  "content-length",
]);

// Agents reach the tools server and its authorization server at the console's own address
// (003 FR-001, research R-01): these paths go to the service untouched, before any page.
const AGENT_PATHS = ["/mcp", "/register", "/authorize", "/token", "/revoke"];

export function isAgentPath(pathname: string): boolean {
  return AGENT_PATHS.includes(pathname) || pathname.startsWith("/.well-known/");
}

function serviceUrl(): string {
  return (process.env.PONO_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
}

function forwardHeaders(source: Headers): Headers {
  const headers = new Headers();
  source.forEach((value, name) => {
    if (!HOP_BY_HOP.has(name.toLowerCase())) headers.append(name, value);
  });
  return headers;
}

export async function relay(request: Request): Promise<Response> {
  const incoming = new URL(request.url);
  const target = `${serviceUrl()}${incoming.pathname}${incoming.search}`;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers: forwardHeaders(request.headers),
      body: hasBody ? await request.arrayBuffer() : undefined,
      // Sign-in and authorization redirects must reach the client untouched, with their cookies.
      redirect: "manual",
    });
  } catch {
    return Response.json({ error: { code: "service.unreachable" } }, { status: 503 });
  }

  const headers = forwardHeaders(upstream.headers);
  // Headers.forEach folds repeated Set-Cookie into one line; restore each cookie separately.
  headers.delete("set-cookie");
  for (const cookie of upstream.headers.getSetCookie()) headers.append("set-cookie", cookie);

  return new Response(upstream.body, { status: upstream.status, headers });
}
