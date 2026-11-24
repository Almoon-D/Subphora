#!/usr/bin/env bash
# Copyright (c) 2026 Almoon-D. All rights reserved.
# Claude Code SessionStart hook (.claude/settings.json), on start and on resume: in a cloud
# session, bring uv and Python to their newest releases, put the Node of .nvmrc on the PATH,
# point Playwright at the Chromium the cloud image ships, and install the locked
# environments (~30 s) before the agent starts. Local sessions are left alone: the owner's
# machine runs `make setup` when it needs to.
set -uo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-.}"
log="${TMPDIR:-/tmp}/make-setup.log"
: >"$log"

# Node: the newest release of the major in .nvmrc, unless the PATH already has it.
major="$(grep -m1 -E '^[0-9]+' "$root/.nvmrc")"
if [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null)" != "$major" ]; then
  dir="$HOME/.local/opt/node-$major"
  if [ ! -x "$dir/bin/node" ]; then
    mkdir -p "$dir"
    url="https://nodejs.org/dist/latest-v$major.x"
    tarball="$(curl -fsSL "$url/SHASUMS256.txt" | grep -o "node-v[0-9.]*-linux-x64.tar.xz" | head -1)"
    curl -fsSL "$url/$tarball" | tar -xJ -C "$dir" --strip-components=1 >>"$log" 2>&1
  fi
  export PATH="$dir/bin:$PATH"
  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "export PATH=\"$dir/bin:\$PATH\"" >>"$CLAUDE_ENV_FILE"
fi

# The cloud image's Chromium belongs to another Playwright release than web/'s.
chromium="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}/chromium"
if [ -x "$chromium" ]; then
  export PLAYWRIGHT_CHROMIUM_EXECUTABLE="$chromium"
  [ -n "${CLAUDE_ENV_FILE:-}" ] && echo "export PLAYWRIGHT_CHROMIUM_EXECUTABLE=\"$chromium\"" >>"$CLAUDE_ENV_FILE"
fi

if make -C "$root" setup >>"$log" 2>&1; then
  echo "Environment ready: make setup succeeded (Node $(node --version))."
else
  echo "make setup failed; see $log before running make check."
fi
exit 0
