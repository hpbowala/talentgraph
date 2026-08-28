import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { type Session, SessionContext } from "./session-context";
import {
  authEnabled,
  currentUsername,
  getAccessToken,
  setUnauthorizedHandler,
  signOut as cognitoSignOut,
} from "./auth";

export function SessionProvider({ children }: { children: React.ReactNode }) {
  // With no pool there is nothing to check, so skip straight to a settled state
  // rather than rendering the checking placeholder forever.
  const [status, setStatus] = useState<Session["status"]>(authEnabled ? "checking" : "out");
  const navigate = useNavigate();

  useEffect(() => {
    if (!authEnabled) return;
    let cancelled = false;
    void getAccessToken().then((token) => {
      if (!cancelled) setStatus(token ? "in" : "out");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // A 401 mid-session means the refresh token is spent: drop the session and
  // send the user to the login page rather than surfacing it as a chat error.
  useEffect(() => {
    if (!authEnabled) return;
    setUnauthorizedHandler(() => {
      setStatus("out");
      navigate("/login", { replace: true });
    });
  }, [navigate]);

  const signIn = useCallback(() => setStatus("in"), []);

  const signOut = useCallback(() => {
    cognitoSignOut();
    setStatus("out");
    navigate("/", { replace: true });
  }, [navigate]);

  const value = useMemo<Session>(
    () => ({
      status,
      required: authEnabled,
      username: authEnabled && status === "in" ? currentUsername() : null,
      signIn,
      signOut,
    }),
    [status, signIn, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
