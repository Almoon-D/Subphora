// Copyright (c) 2026 Almoon-D. All rights reserved.
// The page behind the login: the app once the server says who is signed in (or cannot be
// reached), the sign-in form when it answers 401.
import { type ReactNode, type SubmitEvent, useEffect, useState } from "react";

import { t } from "../i18n/index.ts";
import { checkSession, type SessionState, signIn } from "./session.ts";

export function Gate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState | "checking">("checking");

  useEffect(() => {
    let live = true;
    void checkSession().then((found) => {
      if (live) {
        setState(found);
      }
    });
    return () => {
      live = false;
    };
  }, []);

  if (state === "checking") {
    return <p className="gate-note">{t("auth.checking")}</p>;
  }
  if (state === "signed_out") {
    return (
      <SignIn
        onSignedIn={() => {
          setState("signed_in");
        }}
      />
    );
  }
  return children;
}

function SignIn({ onSignedIn }: { onSignedIn: () => void }) {
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    void signIn(name, password).then((result) => {
      setBusy(false);
      if (result.ok) {
        onSignedIn();
        return;
      }
      setPassword("");
      if (result.reason === "locked") {
        setError(t("auth.locked", { minutes: Math.ceil(result.retryAfterS / 60) }));
      } else if (result.reason === "wrong") {
        setError(t("auth.wrong"));
      } else if (result.reason === "offline") {
        setError(t("auth.offline"));
      } else {
        setError(t("auth.serverError"));
      }
    });
  };

  return (
    <main className="sign-in">
      <form onSubmit={submit} aria-labelledby="sign-in-title">
        <h1 id="sign-in-title">{t("app.title")}</h1>
        <p className="note">{t("auth.intro")}</p>
        <label>
          {t("auth.name")}
          <input
            name="username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={name}
            onChange={(e) => {
              setName(e.target.value);
            }}
          />
        </label>
        <label>
          {t("auth.password")}
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
            }}
          />
        </label>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={busy || !name.trim() || !password}>
          {busy ? t("auth.signingIn") : t("auth.signIn")}
        </button>
      </form>
    </main>
  );
}
