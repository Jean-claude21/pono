# Pono development runtime, version {{VERSION}} (proposed by Pono; see .pono/runtime/).
# Fluxio's proven container: node and pnpm pinned explicitly, dependencies installed at build time,
# then the gate serves Vite with hot reload. Nothing here holds a secret: the host injects them.
FROM node:22-bookworm-slim

# git and openssh-client let the gate follow the development branch with a read-only deploy key.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates openssh-client \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g pnpm@{{PNPM_VERSION}}

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yam[l] ./
RUN pnpm install --frozen-lockfile

COPY . .

EXPOSE 3000
CMD ["node", ".pono/runtime/gate.mjs"]
