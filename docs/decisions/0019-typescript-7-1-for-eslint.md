# 0019 — TypeScript 7.1 for ESLint as soon as it is stable; no TypeScript 6

- Date: 2026-11-24 · Status: accepted · Owner ruling · Supersedes the parser part of 0016
- Context: typescript-eslint 8.74 reads TypeScript 7 from 7.1 on (its `@typescript/native`
  peer); 7.1 was due on 2026-11-24 and is late (only `7.1.0-beta` and nightlies exist).
- Ruling: the project moves to TypeScript 7.1 the day it is a stable release, for the
  compiler and for ESLint's parser, and drops the `typescript` 6.0 package then. No return
  to TypeScript 6 for anything. Until 7.1 is out, 0016's set-up stays as it is.
- Who: the first session that starts after 7.1 is stable makes the switch as its first
  commit (`web/package.json`, `web/eslint.config.js`, the Dependabot `ignore`).

Copyright (c) 2026 Almoon-D. All rights reserved.
