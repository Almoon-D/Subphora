// Copyright (c) 2026 Almoon-D. All rights reserved.
import { describe, expect, it } from "vitest";

import { checkSession, signIn } from "./session.ts";

const answer = (status: number, body: unknown = {}, headers: Record<string, string> = {}) =>
  (() => Promise.resolve(new Response(JSON.stringify(body), { status, headers }))) as unknown as typeof fetch;
const offline = (() => Promise.reject(new TypeError("Failed to fetch"))) as unknown as typeof fetch;

describe("checkSession", () => {
  it("is signed in when the server names the user", async () => {
    expect(await checkSession(answer(200, { name: "ana" }))).toBe("signed_in");
  });

  it("asks to sign in only on 401", async () => {
    expect(await checkSession(answer(401, { code: "unauthenticated" }))).toBe("signed_out");
  });

  it("lets the app open with no network or a failing server", async () => {
    expect(await checkSession(offline)).toBe("unknown");
    expect(await checkSession(answer(502))).toBe("unknown");
  });
});

describe("signIn", () => {
  it("signs in with the name the server gives back", async () => {
    expect(await signIn(" Ana ", "a long password", answer(200, { name: "ana" }))).toEqual({ ok: true, name: "ana" });
  });

  it("tells a wrong password, a lockout, no network and a server failure apart", async () => {
    expect(await signIn("ana", "x", answer(401, { code: "wrong_credentials" }))).toEqual({ ok: false, reason: "wrong" });
    expect(await signIn("ana", "x", answer(429, {}, { "Retry-After": "120" }))).toEqual({
      ok: false,
      reason: "locked",
      retryAfterS: 120,
    });
    expect(await signIn("ana", "x", answer(429))).toEqual({ ok: false, reason: "locked", retryAfterS: 60 });
    expect(await signIn("ana", "x", offline)).toEqual({ ok: false, reason: "offline" });
    expect(await signIn("ana", "x", answer(503))).toEqual({ ok: false, reason: "server" });
  });
});
