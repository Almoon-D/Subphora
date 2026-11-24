# Maintenance session (monthly, after Dependabot's batch on the 1st)

Model and effort: Sonnet 5.5, high.

1. Open Dependabot pull requests (CI has already merged the green minor, patch and
   security ones; what is left is majors and failures): for each, read the upstream release
   notes for breaking changes. If several are green, check out the newest `main`, combine them on one branch,
   run `make check` once and merge that single PR (one CI run instead of one per update);
   close the originals with a link to it. A red one: fix it, or close it with the reason and,
   if the reason is lasting, add an `ignore` with that reason to `.github/dependabot.yml`.
2. Close Dependabot pull requests that are obsolete (the dependency is already at or past
   that version).
3. Toolchains: patch releases (3.15.2 → 3.15.3) arrive by themselves through `make setup`
   and CI. Is there a newer stable minor Python (or other runtime the project uses)? If so,
   move to it (`.python-version`, `requires-python`, ruff and mypy targets) when its
   dependencies have wheels, with a decision record.
4. Dated values in `config/` (anything with a source and a date): refresh each.
5. ROADMAP: close resolved follow-ups; archive old session-log entries past ~300 lines.
6. Bump the patch version with its CHANGELOG section, then finish with the end-of-session
   protocol in AGENTS.md.
