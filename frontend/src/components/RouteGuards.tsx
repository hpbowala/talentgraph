import { Navigate, useLocation } from "react-router-dom";
import { useSession } from "../session-context";

/** Wraps routes that need a session. Unauthenticated visitors are sent to the
 *  login page, remembering where they were headed so sign-in can resume it. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status, required } = useSession();
  const location = useLocation();

  if (!required) return <>{children}</>;
  if (status === "checking") return <div className="session-check" />;
  if (status === "out") return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

/** Wraps the landing route: a signed-in user has no reason to see it. */
export function RedirectIfSignedIn({ children }: { children: React.ReactNode }) {
  const { status } = useSession();
  if (status === "checking") return <div className="session-check" />;
  if (status === "in") return <Navigate to="/app" replace />;
  return <>{children}</>;
}

/** Wraps the login route. Redirects when signed in, and when no user pool is
 *  configured — the form would only fail on submit, and the app is open. */
export function LoginRoute({ children }: { children: React.ReactNode }) {
  const { status, required } = useSession();
  if (!required) return <Navigate to="/app" replace />;
  if (status === "checking") return <div className="session-check" />;
  if (status === "in") return <Navigate to="/app" replace />;
  return <>{children}</>;
}
