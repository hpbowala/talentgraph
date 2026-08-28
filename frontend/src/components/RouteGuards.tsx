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

/** Wraps the login route. As well as the signed-in case, this covers a URL that
 *  was typed or bookmarked when no user pool is configured: rendering the form
 *  there would only fail on submit with "Authentication is not configured", so
 *  send the visitor to the app instead, which is open in that configuration. */
export function LoginRoute({ children }: { children: React.ReactNode }) {
  const { status, required } = useSession();
  if (!required) return <Navigate to="/app" replace />;
  if (status === "checking") return <div className="session-check" />;
  if (status === "in") return <Navigate to="/app" replace />;
  return <>{children}</>;
}
