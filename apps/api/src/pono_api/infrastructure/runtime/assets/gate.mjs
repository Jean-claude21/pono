// Pono development runtime gate (specs/004-dev-runtime/contracts/runtime-gate.md).
//
// It stands in front of the Vite dev server of this project: only members signed in to Pono reach
// the application; Pono writes files here and they apply at once; the development branch is
// followed without ever overwriting a write not yet saved; compilation and browser errors are
// kept for Pono to read; Vite sleeps after a quiet while and wakes on the next request.
// Node built-ins only: this file runs before and without the project's dependencies.

import { execFile, fork } from "node:child_process";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

export const GATE_VERSION = 1;
const COOKIE = "pono_runtime";
const COOKIE_LIFETIME_SECONDS = 12 * 3600;
const MAX_WRITE_BYTES = 1024 * 1024;
const MAX_ERRORS = 50;
const REFUSED_PREFIXES = [".git/", ".pono/runtime/", "node_modules/"];
const EXAMPLE_ENV = new Set([".env.example", ".env.sample", ".env.template"]);

// --- paths (same rules as the service's domain) --------------------------------------------------

export function writablePath(candidate) {
  const cleaned = String(candidate ?? "").trim().replaceAll("\\", "/");
  if (!cleaned || cleaned.startsWith("/") || cleaned.includes("\0")) return null;
  const normalized = path.posix.normalize(cleaned).replace(/\/$/, "");
  if (normalized === "." || normalized === ".." || normalized.startsWith("../")) return null;
  const parts = normalized.split("/");
  if (REFUSED_PREFIXES.some((prefix) => `${normalized}/`.startsWith(prefix))) return null;
  if (parts.includes(".git")) return null;
  const name = parts.at(-1);
  if ((name === ".env" || name.startsWith(".env.")) && !EXAMPLE_ENV.has(name)) return null;
  return normalized;
}

// --- tickets and the session cookie ----------------------------------------------------------------

const b64 = (buffer) => Buffer.from(buffer).toString("base64url");
const sign = (token, message) => b64(createHmac("sha256", token).update(message).digest());

function sameText(a, b) {
  const left = Buffer.from(String(a));
  const right = Buffer.from(String(b));
  return left.length === right.length && timingSafeEqual(left, right);
}

/** The ticket's payload when its signature, runtime and expiry hold; null otherwise. */
export function verifyTicket(ticket, token, runtimeId, nowSeconds = Date.now() / 1000) {
  const [body, signature] = String(ticket ?? "").split(".");
  if (!body || !signature || !sameText(signature, sign(token, body))) return null;
  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString());
    if (payload.r !== runtimeId || !(payload.e > nowSeconds) || !payload.n) return null;
    return payload;
  } catch {
    return null;
  }
}

export function sessionCookie(token, nowSeconds = Date.now() / 1000) {
  const expires = Math.floor(nowSeconds + COOKIE_LIFETIME_SECONDS);
  return `${expires}.${sign(token, `session:${expires}`)}`;
}

export function validSession(value, token, nowSeconds = Date.now() / 1000) {
  const [expires, signature] = String(value ?? "").split(".");
  if (!expires || !signature || !(Number(expires) > nowSeconds)) return false;
  return sameText(signature, sign(token, `session:${expires}`));
}

function cookieOf(header, name) {
  for (const part of String(header ?? "").split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function withoutCookie(header, name) {
  const kept = String(header ?? "")
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part && !part.startsWith(`${name}=`));
  return kept.length ? kept.join("; ") : undefined;
}

export function localReturn(value) {
  const target = String(value ?? "/");
  return target.startsWith("/") && !target.startsWith("//") && !target.includes("\\")
    ? target
    : "/";
}

// --- errors ------------------------------------------------------------------------------------

const SECRET_SHAPES = [
  [/(postgres(?:ql)?:\/\/[^:\s/]+:)[^@\s]+@/gi, "$1***@"],
  [/\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16})\b/g, "***"],
  [/\b((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)[^\s,;'"]+/gi, "$1***"],
];

export function mask(text) {
  let masked = String(text ?? "");
  for (const [shape, replacement] of SECRET_SHAPES) masked = masked.replace(shape, replacement);
  return masked;
}

export class ErrorStore {
  constructor(now = () => new Date()) {
    this.items = new Map();
    this.now = now;
  }

  add({ source, message, file = null, line = null, stack = null }) {
    const entry = {
      source: source === "browser" ? "browser" : "compile",
      message: mask(message).slice(0, 2000),
      file: file ? mask(file).slice(0, 500) : null,
      line: Number.isInteger(line) ? line : null,
      stack: stack ? mask(stack).slice(0, 4000) : null,
    };
    const key = `${entry.source}|${entry.message}|${entry.file}|${entry.line}`;
    const at = this.now().toISOString();
    const known = this.items.get(key);
    if (known) {
      known.count += 1;
      known.lastAt = at;
      known.resolved = false;
      this.items.delete(key);
      this.items.set(key, known);
    } else {
      this.items.set(key, { ...entry, count: 1, firstAt: at, lastAt: at, resolved: false });
    }
    while (this.items.size > MAX_ERRORS) this.items.delete(this.items.keys().next().value);
  }

  /** A successful update: what was broken before it no longer counts as current. */
  resolveAll() {
    for (const item of this.items.values()) item.resolved = true;
  }

  list() {
    return [...this.items.values()].reverse();
  }
}

// --- git ---------------------------------------------------------------------------------------

function git(cwd, args, env, encoding = "utf8") {
  return new Promise((resolve, reject) => {
    // Files are compared byte for byte with the branch: no line-ending conversion, ever.
    const command = ["-c", "core.autocrlf=false", ...args];
    execFile("git", command, { cwd, env, encoding, maxBuffer: 64 * 1024 * 1024 }, (error, out) =>
      error ? reject(error) : resolve(out),
    );
  });
}

async function blobAt(cwd, env, commit, file) {
  try {
    return await git(cwd, ["show", `${commit}:${file}`], env, "buffer");
  } catch {
    return null;
  }
}

async function localBlob(cwd, file) {
  try {
    return await readFile(path.join(cwd, file));
  } catch {
    return null;
  }
}

const same = (a, b) => (a === null || b === null ? a === b : Buffer.compare(a, b) === 0);

/**
 * Follow the branch without overwriting a write not yet saved (research R-06). Returns the files
 * applied and the conflicts now known.
 */
export async function syncOnce({ cwd, branch, env, conflicts }) {
  await git(cwd, ["fetch", "-q", "--depth", "50", "origin", branch], env);
  const remote = (await git(cwd, ["rev-parse", "FETCH_HEAD"], env)).trim();
  const local = (await git(cwd, ["rev-parse", "HEAD"], env).catch(() => "")).trim();
  const applied = [];
  for (const file of [...conflicts]) {
    // A conflict ends once the file on disk is the branch's version again.
    if (same(await localBlob(cwd, file), await blobAt(cwd, env, remote, file))) conflicts.delete(file);
  }
  if (remote === local) return { applied, head: remote };
  const changed = local
    ? (await git(cwd, ["diff", "--name-only", local, remote], env)).split("\n").filter(Boolean)
    : [];
  for (const file of changed) {
    const [base, incoming, onDisk] = await Promise.all([
      blobAt(cwd, env, local, file),
      blobAt(cwd, env, remote, file),
      localBlob(cwd, file),
    ]);
    if (same(onDisk, incoming)) continue;
    if (!same(onDisk, base)) {
      conflicts.add(file);
      continue;
    }
    const target = path.join(cwd, file);
    if (incoming === null) {
      await rm(target, { force: true });
    } else {
      await mkdir(path.dirname(target), { recursive: true });
      await writeFile(target, incoming);
    }
    applied.push(file);
  }
  await git(cwd, ["reset", "-q", "--mixed", remote], env);
  return { applied, head: remote };
}

// --- the gate ----------------------------------------------------------------------------------

const REPORTER = `(() => {
  const send = (payload) => {
    try {
      const body = JSON.stringify(payload);
      if (navigator.sendBeacon) navigator.sendBeacon("/__pono/report", new Blob([body], { type: "application/json" }));
      else fetch("/__pono/report", { method: "POST", headers: { "content-type": "application/json" }, body, keepalive: true });
    } catch {}
  };
  addEventListener("error", (event) => send({ message: String(event.message || event.error), stack: (event.error && event.error.stack) || null, file: event.filename || null, line: event.lineno || null }));
  addEventListener("unhandledrejection", (event) => { const reason = event.reason; send({ message: String((reason && reason.message) || reason), stack: (reason && reason.stack) || null }); });
})();`;

const WAITING_PAGE = `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="2">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pono</title></head>
<body style="font-family:system-ui,sans-serif;display:grid;place-items:center;min-height:90vh;color:#3c4248">
<p>Réveil du runtime… · Waking up the runtime…</p></body></html>`;

export function createGate(options) {
  const {
    cwd = process.cwd(),
    port = 3000,
    vitePort = 5173,
    token,
    runtimeId,
    projectId = "",
    consoleUrl = "",
    branch = "dev",
    sleepCheckMs = 30_000,
    syncEveryMs = 5000,
    gitEnv = process.env,
    databaseHost = null,
    startDev,
    install = () => Promise.resolve(),
    now = () => new Date(),
  } = options;
  if (!token || !runtimeId) throw new Error("PONO_RUNTIME_TOKEN and PONO_RUNTIME_ID are required");

  const errors = new ErrorStore(now);
  const conflicts = new Set();
  const nonces = new Map();
  let head = null;
  let dev = null;
  let starting = null;
  let lastActivity = now();
  let syncing = false;

  const touch = () => {
    lastActivity = now();
  };
  const seconds = () => now().getTime() / 1000;
  const awake = () => dev !== null && starting === null;

  function wake() {
    if (dev || starting) return starting ?? Promise.resolve();
    starting = (async () => {
      const child = await startDev({
        onError: (error) => errors.add(error),
        onUpdate: () => errors.resolveAll(),
      });
      dev = child;
      child.onExit?.((code) => {
        if (dev === child) {
          dev = null;
          if (code) errors.add({ source: "compile", message: `dev server exited (${code})` });
        }
      });
    })()
      .catch((error) => {
        errors.add({ source: "compile", message: `dev server failed to start: ${error.message}` });
      })
      .finally(() => {
        starting = null;
      });
    return starting;
  }

  async function sleep() {
    const child = dev;
    dev = null;
    await child?.stop();
  }

  async function sync() {
    if (syncing) return;
    syncing = true;
    try {
      const result = await syncOnce({ cwd, branch, env: gitEnv, conflicts });
      head = result.head;
      if (result.applied.includes("pnpm-lock.yaml")) {
        await install();
        if (dev) {
          await sleep();
          await wake();
        }
      }
    } catch (error) {
      errors.add({ source: "compile", message: `branch sync failed: ${error.message}` });
    } finally {
      syncing = false;
    }
  }

  function bearer(request) {
    return sameText(request.headers.authorization ?? "", `Bearer ${token}`);
  }

  function member(request) {
    return validSession(cookieOf(request.headers.cookie, COOKIE), token, seconds());
  }

  function send(response, status, body, headers = {}) {
    const payload = body === undefined ? "" : typeof body === "string" ? body : JSON.stringify(body);
    response.writeHead(status, {
      "content-type": typeof body === "string" ? "text/plain; charset=utf-8" : "application/json",
      "cache-control": "no-store",
      ...headers,
    });
    response.end(payload);
  }

  async function bodyOf(request, limit) {
    const chunks = [];
    let size = 0;
    for await (const chunk of request) {
      size += chunk.length;
      if (size > limit) throw Object.assign(new Error("too large"), { status: 413 });
      chunks.push(chunk);
    }
    return Buffer.concat(chunks);
  }

  async function writeFileRequest(request, response) {
    let payload;
    try {
      payload = JSON.parse((await bodyOf(request, MAX_WRITE_BYTES * 2)).toString() || "{}");
    } catch (error) {
      return send(response, error.status ?? 400, { code: "request.invalid" });
    }
    const file = writablePath(payload.path);
    if (!file) return send(response, 422, { code: "runtime.path_refused" });
    const target = path.join(cwd, file);
    if (payload.delete === true) {
      await rm(target, { force: true });
    } else {
      const content = Buffer.from(String(payload.content ?? ""), "base64");
      if (content.length > MAX_WRITE_BYTES) {
        return send(response, 413, { code: "runtime.file_too_large" });
      }
      await mkdir(path.dirname(target), { recursive: true });
      const temporary = `${target}.pono-${randomBytes(4).toString("hex")}`;
      await writeFile(temporary, content);
      await rename(temporary, target);
    }
    touch();
    void wake();
    response.writeHead(204).end();
  }

  function status(response) {
    send(response, 200, {
      awake: awake(),
      lastActivityAt: lastActivity.toISOString(),
      head,
      conflicts: [...conflicts].sort(),
      errors: errors.list(),
      databaseHost,
      version: GATE_VERSION,
    });
  }

  function authenticate(url, response) {
    const ticket = url.searchParams.get("ticket");
    const payload = verifyTicket(ticket, token, runtimeId, seconds());
    if (!payload || nonces.has(payload.n)) return send(response, 403, "forbidden");
    nonces.set(payload.n, payload.e);
    for (const [nonce, expires] of nonces) if (expires < seconds()) nonces.delete(nonce);
    const secure = options.secureCookie === false ? "" : "; Secure";
    response.writeHead(302, {
      location: localReturn(url.searchParams.get("return")),
      "set-cookie": `${COOKIE}=${sessionCookie(token, seconds())}; Path=/; HttpOnly; SameSite=Lax${secure}; Max-Age=${COOKIE_LIFETIME_SECONDS}`,
      "cache-control": "no-store",
    });
    response.end();
  }

  function toConsole(url, response) {
    const target = new URL("/runtime/open", consoleUrl || "http://localhost");
    target.searchParams.set("project", projectId);
    target.searchParams.set("return", localReturn(`${url.pathname}${url.search}`));
    response.writeHead(302, { location: target.toString(), "cache-control": "no-store" });
    response.end();
  }

  function forward(request, response) {
    const headers = { ...request.headers, "accept-encoding": "identity" };
    const cookies = withoutCookie(headers.cookie, COOKIE);
    if (cookies) headers.cookie = cookies;
    else delete headers.cookie;
    const upstream = http.request(
      { host: "127.0.0.1", port: vitePort, method: request.method, path: request.url, headers },
      (answer) => {
        const type = String(answer.headers["content-type"] ?? "");
        if (!type.includes("text/html")) {
          response.writeHead(answer.statusCode ?? 502, answer.headers);
          answer.pipe(response);
          return;
        }
        const chunks = [];
        answer.on("data", (chunk) => chunks.push(chunk));
        answer.on("end", () => {
          const tag = '<script src="/__pono/reporter.js" defer></script>';
          const html = Buffer.concat(chunks).toString();
          const injected = html.includes("</head>")
            ? html.replace("</head>", `${tag}</head>`)
            : `${tag}${html}`;
          const outgoing = { ...answer.headers };
          delete outgoing["content-length"];
          delete outgoing["transfer-encoding"];
          response.writeHead(answer.statusCode ?? 200, outgoing);
          response.end(injected);
        });
      },
    );
    upstream.on("error", () => {
      if (!response.headersSent) send(response, 502, "dev server unavailable");
      else response.destroy();
    });
    request.pipe(upstream);
  }

  async function handle(request, response) {
    const url = new URL(request.url ?? "/", "http://gate");
    if (url.pathname.startsWith("/__pono/")) {
      if (url.pathname === "/__pono/status" && request.method === "GET") {
        return bearer(request) ? status(response) : send(response, 401, { code: "auth" });
      }
      if (url.pathname === "/__pono/files" && request.method === "PUT") {
        return bearer(request) ? writeFileRequest(request, response) : send(response, 401, { code: "auth" });
      }
      if (url.pathname === "/__pono/auth" && request.method === "GET") return authenticate(url, response);
      if (!member(request)) return send(response, 401, { code: "auth" });
      if (url.pathname === "/__pono/reporter.js") {
        return send(response, 200, REPORTER, { "content-type": "text/javascript; charset=utf-8" });
      }
      if (url.pathname === "/__pono/report" && request.method === "POST") {
        try {
          const report = JSON.parse((await bodyOf(request, 64 * 1024)).toString());
          errors.add({ ...report, source: "browser", line: Number(report.line) || null });
        } catch {
          // A malformed report is dropped: it must never break the page.
        }
        return response.writeHead(204).end();
      }
      return send(response, 404, { code: "not_found" });
    }
    if (!member(request)) return toConsole(url, response);
    touch();
    if (!awake()) {
      void wake();
      if (String(request.headers.accept ?? "").includes("text/html")) {
        return send(response, 503, WAITING_PAGE, {
          "content-type": "text/html; charset=utf-8",
          "retry-after": "2",
        });
      }
      return send(response, 503, "waking up", { "retry-after": "2" });
    }
    forward(request, response);
  }

  function upgrade(request, socket, head_) {
    if (!member(request)) {
      socket.end("HTTP/1.1 401 Unauthorized\r\n\r\n");
      return;
    }
    if (!awake()) {
      void wake();
      socket.end("HTTP/1.1 503 Service Unavailable\r\n\r\n");
      return;
    }
    const upstream = net.connect(vitePort, "127.0.0.1", () => {
      const lines = [`${request.method} ${request.url} HTTP/${request.httpVersion}`];
      for (let index = 0; index < request.rawHeaders.length; index += 2) {
        const name = request.rawHeaders[index];
        if (name.toLowerCase() === "cookie") {
          const kept = withoutCookie(request.rawHeaders[index + 1], COOKIE);
          if (kept) lines.push(`${name}: ${kept}`);
        } else {
          lines.push(`${name}: ${request.rawHeaders[index + 1]}`);
        }
      }
      upstream.write(`${lines.join("\r\n")}\r\n\r\n`);
      if (head_?.length) upstream.write(head_);
      upstream.pipe(socket);
      socket.pipe(upstream);
    });
    upstream.on("error", () => socket.destroy());
    socket.on("error", () => upstream.destroy());
  }

  const server = http.createServer((request, response) => {
    handle(request, response).catch(() => {
      if (!response.headersSent) send(response, 500, { code: "gate.error" });
    });
  });
  server.on("upgrade", upgrade);

  const timers = [];
  return {
    server,
    errors,
    conflicts,
    sync,
    wake,
    awake,
    async start() {
      await new Promise((resolve) => server.listen(port, "0.0.0.0", resolve));
      await sync();
      await wake();
      timers.push(setInterval(() => void sync(), syncEveryMs));
      timers.push(
        setInterval(() => {
          // Read at each tick: the delay can change while the gate runs.
          const sleepAfterMs = options.sleepAfterMs ?? 15 * 60 * 1000;
          if (awake() && now().getTime() - lastActivity.getTime() > sleepAfterMs) void sleep();
        }, sleepCheckMs),
      );
    },
    async close() {
      for (const timer of timers) clearInterval(timer);
      await sleep();
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

// --- running inside the runtime's container ------------------------------------------------------

function forkDev(cwd, vitePort) {
  return ({ onError, onUpdate }) =>
    new Promise((resolve, reject) => {
      const script = fileURLToPath(new URL("./dev.mjs", import.meta.url));
      const child = fork(script, [], {
        cwd,
        env: { ...process.env, PONO_VITE_PORT: String(vitePort) },
        stdio: ["ignore", "inherit", "inherit", "ipc"],
      });
      const exits = [];
      const timeout = setTimeout(() => reject(new Error("dev server took too long")), 120_000);
      child.on("message", (message) => {
        if (message?.type === "ready") {
          clearTimeout(timeout);
          resolve({
            onExit: (listener) => exits.push(listener),
            stop: () =>
              new Promise((done) => {
                child.once("exit", done);
                child.kill("SIGTERM");
              }),
          });
        } else if (message?.type === "error") onError(message);
        else if (message?.type === "update") onUpdate();
      });
      child.on("exit", (code) => {
        clearTimeout(timeout);
        for (const listener of exits) listener(code);
        reject(new Error(`dev server exited (${code})`));
      });
    });
}

async function prepareRepository(cwd, cloneUrl, branch, env) {
  if (!existsSync(path.join(cwd, ".git"))) await git(cwd, ["init", "-q"], env);
  await git(cwd, ["remote", "remove", "origin"], env).catch(() => undefined);
  await git(cwd, ["remote", "add", "origin", cloneUrl], env);
  await git(cwd, ["fetch", "-q", "--depth", "50", "origin", branch], env);
  const hasHead = await git(cwd, ["rev-parse", "--verify", "HEAD"], env).then(
    () => true,
    () => false,
  );
  // The image was built from the branch: take its head as the base, keep the files as they are.
  if (!hasHead) await git(cwd, ["reset", "-q", "--mixed", "FETCH_HEAD"], env);
}

async function sshEnvironment(keyBase64) {
  if (!keyBase64) return process.env;
  const home = process.env.HOME || "/root";
  const directory = path.join(home, ".ssh");
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const keyFile = path.join(directory, "pono_runtime_key");
  await writeFile(keyFile, Buffer.from(keyBase64, "base64"), { mode: 0o600 });
  return {
    ...process.env,
    GIT_SSH_COMMAND: `ssh -i ${keyFile} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=${path.join(directory, "known_hosts")}`,
  };
}

function hostOf(databaseUrl) {
  try {
    return databaseUrl ? new URL(databaseUrl).hostname : null;
  } catch {
    return null;
  }
}

async function main() {
  const cwd = process.cwd();
  const branch = process.env.PONO_BRANCH || "dev";
  const env = await sshEnvironment(process.env.PONO_DEPLOY_KEY_B64);
  if (process.env.PONO_CLONE_URL) {
    await prepareRepository(cwd, process.env.PONO_CLONE_URL, branch, env).catch((error) => {
      console.error(`[pono] repository not prepared: ${error.message}`);
    });
  }
  const vitePort = 5173;
  const gate = createGate({
    cwd,
    port: Number(process.env.PORT || 3000),
    vitePort,
    token: process.env.PONO_RUNTIME_TOKEN,
    runtimeId: process.env.PONO_RUNTIME_ID,
    projectId: process.env.PONO_PROJECT_ID,
    consoleUrl: process.env.PONO_CONSOLE_URL,
    branch,
    sleepAfterMs: Number(process.env.PONO_SLEEP_AFTER_SECONDS || 900) * 1000,
    gitEnv: env,
    databaseHost: hostOf(process.env.DATABASE_URL),
    startDev: forkDev(cwd, vitePort),
    install: () =>
      new Promise((resolve) => {
        execFile("pnpm", ["install", "--prefer-offline"], { cwd, env }, () => resolve());
      }),
  });
  await gate.start();
  console.log(`[pono] gate ${GATE_VERSION} listening; following ${branch}`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`[pono] gate failed: ${error.message}`);
    process.exit(1);
  });
}
