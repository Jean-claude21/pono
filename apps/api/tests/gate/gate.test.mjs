// T007, T016, T021, T024, T025 — the runtime's gate, against a real Git remote in a temporary
// folder and a stand-in for Vite. Run with `node --test apps/api/tests/gate/`.

import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { after, before, describe, it } from "node:test";

import {
  ErrorStore,
  createGate,
  mask,
  syncOnce,
  verifyTicket,
  writablePath,
} from "../../src/pono_api/infrastructure/runtime/assets/gate.mjs";

const TOKEN = "gate-test-token";
const RUNTIME = "01990000-0000-7000-8000-00000000a001";
// Signed by the service's domain code (pono_api.domain.runtimes.RuntimeTicket), same token, same
// runtime: the two sides must agree byte for byte.
const PYTHON_VECTOR =
  "eyJyIjoiMDE5OTAwMDAtMDAwMC03MDAwLTgwMDAtMDAwMDAwMDBhMDAxIiwiZSI6NDEwMjQ0NDgwMCwibiI6Im4xIn0.5d3tNEL6EPLxWc-2pHBeUWXDll2XEMd_Ap3sd6a_GiY";

const GIT = [
  "-c", "user.name=test", "-c", "user.email=test@pono.test",
  "-c", "init.defaultBranch=dev", "-c", "core.autocrlf=false",
];
const run = (cwd, ...args) => execFileSync("git", [...GIT, ...args], { cwd, encoding: "utf8" });

function ticket(runtime = RUNTIME, expires = Date.now() / 1000 + 60, nonce = Math.random().toString(36)) {
  const body = Buffer.from(JSON.stringify({ r: runtime, e: Math.floor(expires), n: nonce })).toString(
    "base64url",
  );
  const signature = createHmac("sha256", TOKEN).update(body).digest("base64url");
  return `${body}.${signature}`;
}

function freePort() {
  return new Promise((resolve) => {
    const probe = net.createServer().listen(0, "127.0.0.1", () => {
      const { port } = probe.address();
      probe.close(() => resolve(port));
    });
  });
}

describe("pure rules", () => {
  it("normalizes project paths and refuses protected ones, like the service", () => {
    assert.equal(writablePath("./src//a.ts"), "src/a.ts");
    assert.equal(writablePath(".env.example"), ".env.example");
    for (const refused of ["", "/etc/passwd", "../x", "src/../../x", ".git/config", "a/.git/b",
      ".pono/runtime/gate.mjs", "node_modules/x", ".env", "apps/.env.local"]) {
      assert.equal(writablePath(refused), null, refused);
    }
  });

  it("accepts the ticket the service signs, and nothing else", () => {
    assert.equal(verifyTicket(PYTHON_VECTOR, "vector-token", RUNTIME, 0).n, "n1");
    assert.equal(verifyTicket(PYTHON_VECTOR, "vector-token", "another", 0), null);
    assert.equal(verifyTicket(PYTHON_VECTOR, "wrong-token", RUNTIME, 0), null);
    assert.equal(verifyTicket(PYTHON_VECTOR, "vector-token", RUNTIME, 4102444801), null);
  });

  it("masks secrets and keeps errors deduplicated, newest first", () => {
    assert.equal(
      mask("connect postgresql://owner:hunter2@ep.neon.tech/db token=abc123"),
      "connect postgresql://owner:***@ep.neon.tech/db token=***",
    );
    const store = new ErrorStore();
    store.add({ source: "compile", message: "boom", file: "a.ts", line: 3 });
    store.add({ source: "compile", message: "boom", file: "a.ts", line: 3 });
    store.add({ source: "browser", message: "later" });
    assert.deepEqual(store.list().map((e) => [e.message, e.count]), [["later", 1], ["boom", 2]]);
    store.resolveAll();
    assert.ok(store.list().every((e) => e.resolved));
  });
});

describe("the gate in front of the dev server", () => {
  let root;
  let remote;
  let seed;
  let work;
  let gate;
  let base;
  let seen;
  let devServer;
  let vitePort;
  let starts = 0;
  let options;

  before(async () => {
    root = mkdtempSync(path.join(os.tmpdir(), "pono-gate-"));
    remote = path.join(root, "remote.git");
    seed = path.join(root, "seed");
    work = path.join(root, "work");
    run(root, "init", "-q", "--bare", remote);
    run(root, "clone", "-q", remote, seed);
    writeFileSync(path.join(seed, "index.ts"), "export const version = 1;\n");
    writeFileSync(path.join(seed, "shared.ts"), "export const shared = 1;\n");
    run(seed, "add", ".");
    run(seed, "commit", "-q", "-m", "first");
    run(seed, "push", "-q", "origin", "HEAD:dev");
    run(root, "clone", "-q", "-b", "dev", remote, work);

    vitePort = await freePort();
    seen = [];
    const startDev = () =>
      new Promise((resolve) => {
        starts += 1;
        devServer = http.createServer((request, response) => {
          seen.push(request.headers);
          if (request.url === "/") {
            response.writeHead(200, { "content-type": "text/html" });
            response.end("<html><head><title>app</title></head><body>app</body></html>");
          } else {
            response.writeHead(200, { "content-type": "text/javascript" });
            response.end("export default 1;");
          }
        });
        devServer.on("upgrade", (_request, socket) => {
          socket.end("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n");
        });
        devServer.listen(vitePort, "127.0.0.1", () =>
          resolve({ stop: () => new Promise((done) => devServer.close(done)) }),
        );
      });

    options = {
      cwd: work,
      port: 0,
      vitePort,
      token: TOKEN,
      runtimeId: RUNTIME,
      projectId: "p-1",
      consoleUrl: "https://console.test",
      branch: "dev",
      sleepAfterMs: 60_000,
      sleepCheckMs: 50,
      syncEveryMs: 60_000,
      databaseHost: "ep-dev.neon.tech",
      startDev,
      secureCookie: false,
    };
    gate = createGate(options);
    await gate.start();
    base = `http://127.0.0.1:${gate.server.address().port}`;
  });

  after(async () => {
    await gate?.close();
    rmSync(root, { recursive: true, force: true });
  });

  async function signIn() {
    const answer = await fetch(`${base}/__pono/auth?ticket=${ticket()}&return=/`, { redirect: "manual" });
    assert.equal(answer.status, 302);
    return answer.headers.get("set-cookie").split(";")[0];
  }

  it("sends a visitor without a session to Pono, and serves nothing of the application", async () => {
    const answer = await fetch(`${base}/src/secret.ts?x=1`, { redirect: "manual" });
    assert.equal(answer.status, 302);
    const target = new URL(answer.headers.get("location"));
    assert.equal(`${target.origin}${target.pathname}`, "https://console.test/runtime/open");
    assert.equal(target.searchParams.get("project"), "p-1");
    assert.equal(target.searchParams.get("return"), "/src/secret.ts?x=1");
    assert.doesNotMatch(await answer.text(), /export/);
  });

  it("opens with a one-time ticket, and a ticket for another runtime or used twice opens nothing", async () => {
    const once = ticket();
    const first = await fetch(`${base}/__pono/auth?ticket=${once}&return=//evil.test`, { redirect: "manual" });
    assert.equal(first.status, 302);
    assert.equal(first.headers.get("location"), "/");
    assert.match(first.headers.get("set-cookie"), /pono_runtime=.*HttpOnly/);
    const again = await fetch(`${base}/__pono/auth?ticket=${once}`, { redirect: "manual" });
    assert.equal(again.status, 403);
    const other = await fetch(`${base}/__pono/auth?ticket=${ticket("another")}`, { redirect: "manual" });
    assert.equal(other.status, 403);
  });

  it("serves a member the application, with the error reporter, without passing its cookie on", async () => {
    const cookie = await signIn();
    const page = await fetch(`${base}/`, { headers: { cookie: `${cookie}; app=1` } });
    const html = await page.text();
    assert.equal(page.status, 200);
    assert.match(html, /<script src="\/__pono\/reporter.js" defer><\/script><\/head>/);
    assert.equal(seen.at(-1).cookie, "app=1");
    const reporter = await fetch(`${base}/__pono/reporter.js`, { headers: { cookie } });
    assert.match(await reporter.text(), /unhandledrejection/);
  });

  it("refuses the hot reload socket without a session", async () => {
    const answer = await new Promise((resolve) => {
      const socket = net.connect(gate.server.address().port, "127.0.0.1", () => {
        socket.write("GET / HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n");
      });
      socket.on("data", (data) => {
        resolve(data.toString());
        socket.destroy();
      });
    });
    assert.match(answer, /^HTTP\/1.1 401/);
  });

  it("writes and deletes files for the service only, inside the project only", async () => {
    const put = (body, auth = `Bearer ${TOKEN}`) =>
      fetch(`${base}/__pono/files`, {
        method: "PUT",
        headers: { authorization: auth, "content-type": "application/json" },
        body: JSON.stringify(body),
      });
    const content = Buffer.from("export const fresh = 1;\n").toString("base64");
    assert.equal((await put({ path: "src/fresh.ts", content }, "Bearer nope")).status, 401);
    assert.equal((await put({ path: "src/fresh.ts", content })).status, 204);
    assert.equal(readFileSync(path.join(work, "src/fresh.ts"), "utf8"), "export const fresh = 1;\n");
    assert.equal((await put({ path: "../escape.ts", content })).status, 422);
    assert.equal((await put({ path: ".env", content })).status, 422);
    assert.equal((await put({ path: "src/fresh.ts", delete: true })).status, 204);
    assert.equal(existsSync(path.join(work, "src/fresh.ts")), false);
  });

  it("reports its state and the browser's errors, secrets masked", async () => {
    const cookie = await signIn();
    await fetch(`${base}/__pono/report`, {
      method: "POST",
      headers: { cookie, "content-type": "application/json" },
      body: JSON.stringify({ message: "TypeError: x is undefined password=hunter2", line: 12 }),
    });
    const refused = await fetch(`${base}/__pono/status`);
    assert.equal(refused.status, 401);
    const status = await (await fetch(`${base}/__pono/status`, { headers: { authorization: `Bearer ${TOKEN}` } })).json();
    assert.equal(status.databaseHost, "ep-dev.neon.tech");
    assert.equal(status.head, run(work, "rev-parse", "HEAD").trim());
    const browser = status.errors.find((error) => error.source === "browser");
    assert.equal(browser.message, "TypeError: x is undefined password=***");
    assert.equal(browser.line, 12);
  });

  it("follows the branch, and never overwrites a write not yet saved", async () => {
    // An unsaved write in the runtime, then two pushes from elsewhere.
    writeFileSync(path.join(work, "shared.ts"), "export const shared = 'mine';\n");
    writeFileSync(path.join(seed, "index.ts"), "export const version = 2;\n");
    writeFileSync(path.join(seed, "shared.ts"), "export const shared = 'theirs';\n");
    run(seed, "commit", "-q", "-am", "second");
    run(seed, "push", "-q", "origin", "HEAD:dev");

    await gate.sync();

    assert.equal(readFileSync(path.join(work, "index.ts"), "utf8"), "export const version = 2;\n");
    assert.equal(readFileSync(path.join(work, "shared.ts"), "utf8"), "export const shared = 'mine';\n");
    assert.deepEqual([...gate.conflicts], ["shared.ts"]);
    assert.equal(run(work, "rev-parse", "HEAD").trim(), run(seed, "rev-parse", "HEAD").trim());

    // The service saves the write: the branch now holds it, and the conflict ends.
    writeFileSync(path.join(seed, "shared.ts"), "export const shared = 'mine';\n");
    run(seed, "commit", "-q", "-am", "pono: save 1 file");
    run(seed, "push", "-q", "origin", "HEAD:dev");
    await gate.sync();
    assert.deepEqual([...gate.conflicts], []);
  });

  it("applies a pushed file the runtime never touched, and a deletion", async () => {
    const conflicts = new Set();
    run(seed, "rm", "-q", "index.ts");
    writeFileSync(path.join(seed, "added.ts"), "export const added = true;\n");
    run(seed, "add", ".");
    run(seed, "commit", "-q", "-m", "third");
    run(seed, "push", "-q", "origin", "HEAD:dev");

    const result = await syncOnce({ cwd: work, branch: "dev", env: process.env, conflicts });

    assert.deepEqual(result.applied.sort(), ["added.ts", "index.ts"]);
    assert.equal(existsSync(path.join(work, "index.ts")), false);
    assert.equal(conflicts.size, 0);
  });

  it("sleeps after a quiet while and wakes on the next visit", async () => {
    const cookie = await signIn();
    const before = starts;
    options.sleepAfterMs = 150;
    await new Promise((resolve) => setTimeout(resolve, 600));
    options.sleepAfterMs = 60_000;
    assert.equal(gate.awake(), false);
    const waiting = await fetch(`${base}/`, { headers: { cookie, accept: "text/html" } });
    assert.equal(waiting.status, 503);
    assert.match(await waiting.text(), /Waking up the runtime/);
    await gate.wake();
    assert.equal(gate.awake(), true);
    assert.equal(starts, before + 1);
    assert.equal((await fetch(`${base}/`, { headers: { cookie } })).status, 200);
  });
});
