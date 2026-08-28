import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { signIn } from "../auth";
import { useSession } from "../session-context";
import { Brand } from "./Sidebar";

/** The `/login` route. RequireAuth sends visitors here with the page they were
 *  trying to reach in location state, so sign-in can resume it. */
export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const { signIn: markSignedIn } = useSession();
  const from = (location.state as { from?: { pathname: string } } | null)?.from?.pathname;

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !username.trim() || !password) return;
    setBusy(true);
    setError(null);
    try {
      await signIn(username.trim(), password);
      markSignedIn();
      navigate(from ?? "/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <div className="ambient" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
      </div>
      <form className="login-card" onSubmit={submit}>
        <Brand />
        <p className="login-lede">Sign in to query the workforce graph.</p>
        <label className="login-field">
          <span>Username</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            disabled={busy}
            required
          />
        </label>
        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            disabled={busy}
            required
          />
        </label>
        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="login-submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <button
          type="button"
          className="login-back"
          onClick={() => navigate("/")}
          disabled={busy}
        >
          Back
        </button>
      </form>
    </div>
  );
}
