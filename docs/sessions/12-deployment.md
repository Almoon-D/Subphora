# Session 12 — Deployment: version 1 on the phone

Model and effort: Opus 5.5, high.

## Goal

The app runs on the host the owner chooses, over HTTPS, with a login for the family users,
and installs on a phone: the owner completes the version-1 flow in the field.

## Read

- `docs/MASTER_PLAN.md` § 4.8, § 3 (Hosting, Privacy).
- `docs/decisions/` 0007.

## Build

1. Put the hosting options to the owner with current prices (a free tier such as Oracle
   Cloud Always Free, a server of about €5 a month, a home mini PC) and record the choice.
   A paid option needs the owner's approval in that decision.
2. `deploy/`: Docker Compose (API, Caddy for HTTPS and the static PWA), for x86-64 and
   ARM64; the Docker ecosystem in `.github/dependabot.yml`; a step-by-step guide for the
   owner in Spanish.
3. Login: a few users, hashed passwords, secure cookies, a command to add a user; every API
   route behind it.
4. Nightly backups of `data/` to a destination the owner chooses; a restore test.
5. Secrets only from the environment; nothing private in the image.
6. Tests: auth failure branches, the backup and restore commands, the compose file validated.

## DO NOT BUILD

- Multi-tenant features; public sign-up.

## Done when

- `make check` is green and the owner, following the guide, has the app on their host and
  installs it on their phone (VERIFY-LIVE until the owner confirms).
