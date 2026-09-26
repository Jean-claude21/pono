// Pono development runtime: starts this project's Vite dev server behind the gate.
//
// It loads the project's own vite.config and only adds what a server behind a proxy needs (the two
// traps Fluxio hit: unknown hosts refused, HMR socket on the wrong port). Errors Vite sends to the
// browser, and those it logs, are passed to the gate; a successful update clears them.

import { createServer } from "vite";

const port = Number(process.env.PONO_VITE_PORT || 5173);
const tell = (message) => {
  if (process.send) process.send(message);
};
const plain = (text) => String(text ?? "").replace(/\u001b\[[0-9;]*m/g, "");

function shape(error) {
  const location = error?.loc ?? {};
  return {
    type: "error",
    source: "compile",
    message: plain(error?.message ?? error),
    file: location.file ?? error?.id ?? null,
    line: Number.isInteger(location.line) ? location.line : null,
    stack: plain(error?.frame ?? error?.stack ?? "") || null,
  };
}

const server = await createServer({
  server: {
    host: "127.0.0.1",
    port,
    strictPort: true,
    allowedHosts: true,
    hmr: {
      clientPort: Number(process.env.PONO_HMR_CLIENT_PORT || 443),
      protocol: process.env.PONO_HMR_PROTOCOL || "wss",
    },
  },
});

const send = server.ws.send.bind(server.ws);
server.ws.send = (payload, ...rest) => {
  if (payload && typeof payload === "object") {
    if (payload.type === "error") tell(shape(payload.err));
    else if (payload.type === "update" || payload.type === "full-reload") tell({ type: "update" });
  }
  return send(payload, ...rest);
};

const logError = server.config.logger.error.bind(server.config.logger);
server.config.logger.error = (message, options) => {
  tell({ ...shape(options?.error ?? message), message: plain(message) });
  return logError(message, options);
};

await server.listen();
tell({ type: "ready" });

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    server.close().finally(() => process.exit(0));
  });
}
