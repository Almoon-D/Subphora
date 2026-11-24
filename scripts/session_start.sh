#!/usr/bin/env bash
# Copyright (c) 2026 Almoon-D. All rights reserved.
# Claude Code SessionStart hook (.claude/settings.json), on start and on resume: in a cloud
# session, bring uv and Python to their newest releases and install the locked environment
# (~15 s) before the agent starts. `uv run --locked` would build the environment anyway;
# what this adds is fresh toolchains. Local sessions are left alone: the owner's machine
# runs `make setup` when it needs to.
set -uo pipefail
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
log="${TMPDIR:-/tmp}/make-setup.log"
if make -C "${CLAUDE_PROJECT_DIR:-.}" setup >"$log" 2>&1; then
  echo "Environment ready: make setup succeeded."
else
  echo "make setup failed; see $log before running make check."
fi
exit 0
