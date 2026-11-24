#!/usr/bin/env bash
# Copyright (c) 2026 Almoon-D. All rights reserved.
# `make dev`: the API (`subphora serve`) and the Vite development server, which forwards
# /api to it. Ports come from config/defaults/api.yaml (or config/owner.yaml). Ctrl-C
# stops both.
set -euo pipefail
cd "$(dirname "$0")/.."

setting() { uv run --locked subphora config "$1"; }
api_url="http://$(setting api.host):$(setting api.port)"
web_port="$(setting api.dev_web_port)"

uv run --locked subphora serve &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' EXIT

echo "API on $api_url. Open http://localhost:$web_port in the browser."
cd web
SUBPHORA_API_URL="$api_url" npx vite --port "$web_port" --strictPort
