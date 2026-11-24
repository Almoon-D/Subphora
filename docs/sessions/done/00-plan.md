# Session 00 — Plan the project

Model and effort: Opus 5.5, high. The owner is not technical: talk to them in Spanish, in
plain words, one short question at a time. The files you write are in English (AGENTS.md →
Language); summarise them for the owner in Spanish.

## Goal

Turn the owner's idea into a plan that later sessions can build without asking again:
`docs/MASTER_PLAN.md` filled in, the sessions written, and the repository renamed.

## Steps

1. If `scripts/init_project.py` still exists, ask for the project's name and run it
   (`python3 scripts/init_project.py <name> --author "<owner>" --github-user <user>`), then
   `uv lock`.
2. Interview the owner until you can fill every section of `MASTER_PLAN.md`: what it must do
   and for whom; what it must never do; budget (free tiers, paid APIs, LLM spend); data
   sources; where it runs; what "done" looks like. Offer options with a recommendation when
   they do not know; never leave a section empty.
3. Write the one-sentence description of the project in three places: `README.md` (first
   line, in Spanish), `description` in `pyproject.toml` and the package docstring in
   `src/<name>/__init__.py` (in English). Fill `MASTER_PLAN.md`. Its hard limits also go to
   AGENTS.md → Hard rules, each with how code will enforce it; the project's own rules
   (money, time zones, concurrency) go to Constraints.
4. Split the build into sessions, each small enough for one session and ending in something
   the owner can see or run. Write `docs/sessions/01-<slug>.md` onwards in the format of
   `docs/sessions/TEMPLATE.md` (Goal, Read, Build, DO NOT BUILD, Done when, model and effort)
   and list them in ROADMAP → "What runs next".
5. Record the choices that shaped the plan in `docs/decisions/`.

## DO NOT BUILD

- Application code. This session writes the plan; session 01 builds.

## Done when

- The owner has read the session list and agreed to it, and `make check` is green.
- The version stays 0.0.0: session 01 releases 0.1.0. Move this file to `docs/sessions/done/`.
- The report (AGENTS.md → End-of-session protocol) gives the plan in Spanish — the goal, the
  hard limits and every session with what the owner will see at its end — and the prompt
  for session 01.

Copyright (c) 2026 Almoon-D. All rights reserved.
