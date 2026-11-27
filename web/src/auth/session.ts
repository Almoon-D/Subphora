// Copyright (c) 2026 Almoon-D. All rights reserved.
// The login (MASTER_PLAN §4.9): the server keeps the session in a cookie the page cannot
// read, so the page asks who is signed in. Only a 401 means "sign in"; with no network
// (in the field) the app opens on what the device holds, and the outbox waits.

type Fetch = typeof fetch;

export type SessionState = "signed_in" | "signed_out" | "unknown";

export type SignInResult =
  | { ok: true; name: string }
  | { ok: false; reason: "wrong" | "offline" | "server" }
  | { ok: false; reason: "locked"; retryAfterS: number };

export async function checkSession(fetchFn: Fetch = fetch): Promise<SessionState> {
  let response: Response;
  try {
    response = await fetchFn("/api/auth/me", { credentials: "same-origin", cache: "no-store" });
  } catch {
    return "unknown";
  }
  if (response.status === 401) {
    return "signed_out";
  }
  return response.ok ? "signed_in" : "unknown";
}

export async function signIn(name: string, password: string, fetchFn: Fetch = fetch): Promise<SignInResult> {
  let response: Response;
  try {
    response = await fetchFn("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: name.trim(), password }),
    });
  } catch {
    return { ok: false, reason: "offline" };
  }
  if (response.ok) {
    try {
      const body = (await response.json()) as { name?: unknown };
      return { ok: true, name: typeof body.name === "string" ? body.name : name.trim() };
    } catch {
      return { ok: true, name: name.trim() };
    }
  }
  if (response.status === 429) {
    const wait = Number(response.headers.get("Retry-After"));
    return { ok: false, reason: "locked", retryAfterS: Number.isFinite(wait) && wait > 0 ? wait : 60 };
  }
  if (response.status === 401) {
    return { ok: false, reason: "wrong" };
  }
  return { ok: false, reason: "server" };
}
