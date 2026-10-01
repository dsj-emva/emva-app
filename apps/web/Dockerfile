# The screens. Built from the repository root: docker build -f apps/web/Dockerfile .
FROM node:22-slim AS build
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/api-client/package.json packages/api-client/
RUN pnpm install --frozen-lockfile --filter @emva/web...
COPY packages/api-client packages/api-client
COPY apps/web apps/web
RUN pnpm --filter @emva/web build

# Serves the built screens and passes /api to the service at API_URL, as the Vite proxy does locally.
FROM caddy:2-alpine
COPY apps/web/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /repo/apps/web/dist /srv
