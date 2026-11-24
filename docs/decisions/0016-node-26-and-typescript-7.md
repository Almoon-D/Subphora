# 0016 — Node 26 until Node 27 is stable; TypeScript 7 checks, TypeScript 6 parses for ESLint

- Date: 2026-11-24 · Status: accepted · Owner ruling · Corrects a fact of 0011 · MASTER_PLAN §3
- Context: 0011 chose Node 27 over Node 26 LTS. On 2026-11-24 Node 27 exists only as alphas
  (27.0.0-alpha, since 2026-10-29): Node now ships one major a year, stable in April, every
  one becoming LTS. TypeScript 7.0.2 (the native compiler) has no API that typescript-eslint
  8.74 reads: it supports TypeScript up to 6.0 and 7.1 betas.
- Decision: the newest stable Node, 26 (26.13.1 today), in `.nvmrc`; moved to 27 at its
  April 2027 release. `tsc --noEmit` runs TypeScript 7.0 (npm alias `typescript-7`);
  `typescript` 6.0.3 stays installed only as typescript-eslint's parser, until it supports 7.
- Rejected: the Node 27 alpha (Node advises against it; it changes every few weeks);
  TypeScript 6 for everything (a downgrade of the compiler); no type-aware linting.

Copyright (c) 2026 Almoon-D. All rights reserved.
