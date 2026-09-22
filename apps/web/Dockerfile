# Console de Pono — construite depuis la racine du dépôt (contexte « / » dans Coolify),
# parce qu'elle dépend du paquet de l'espace de travail @pono/design.
# Reprend la recette éprouvée par Firmo : build Vite, puis srvx sert le rendu serveur et le statique.

FROM node:22.14.0-bookworm-slim AS build
WORKDIR /app

# pnpm est installé explicitement : la vérification de signature de corepack a déjà cassé des
# builds de l'atelier (leçon Fluxio).
RUN npm install -g pnpm@11.25.0

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/design/package.json packages/design/
RUN pnpm install --frozen-lockfile --filter "@pono/web..."

COPY packages/design packages/design
COPY apps/web apps/web
RUN pnpm --filter @pono/web build

FROM node:22.14.0-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production
RUN groupadd --system pono && useradd --system --gid pono --home-dir /app pono

COPY --from=build --chown=pono:pono /app/node_modules ./node_modules
COPY --from=build --chown=pono:pono /app/packages/design ./packages/design
COPY --from=build --chown=pono:pono /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=build --chown=pono:pono /app/apps/web/package.json ./apps/web/package.json
COPY --from=build --chown=pono:pono /app/apps/web/dist ./apps/web/dist

WORKDIR /app/apps/web
USER pono
EXPOSE 3000

HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 \
  CMD ["node", "-e", "fetch('http://127.0.0.1:3000/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"]

# Le répertoire statique est donné en chemin absolu : srvx ne résout pas toujours un chemin relatif.
CMD ["node_modules/.bin/srvx", "serve", "--entry", "dist/server/server.js", "--static", "/app/apps/web/dist/client", "--prod", "--host", "0.0.0.0", "--port", "3000"]
