# Copyright (c) 2026 Almoon-D. All rights reserved.
# The web image (MASTER_PLAN §4.9): the PWA built by Vite, served by Caddy with HTTPS
# (certificates from Let's Encrypt, renewed by Caddy) in front of the API.
FROM node:26-trixie-slim AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

FROM caddy:2.11-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
