// Copyright (c) 2026 Almoon-D. All rights reserved.
// The Spanish catalogue: every string the page and the PDF report show, in es.json so the
// server reads the same file (decision 0038). `{name}` is replaced by `t`.
import catalogue from "./es.json" with { type: "json" };

export const es: Readonly<typeof catalogue> = catalogue;

export type MessageKey = keyof typeof catalogue;
