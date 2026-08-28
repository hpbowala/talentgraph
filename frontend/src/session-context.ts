import { createContext, useContext } from "react";

export interface Session {
  status: "checking" | "in" | "out";
  /** False when no user pool is configured, i.e. local dev before a deploy.
   *  Route guards let everything through in that case. */
  required: boolean;
  username: string | null;
  signIn: () => void;
  signOut: () => void;
}

/** Kept apart from SessionProvider so that file exports only a component —
 *  mixing the two breaks React Fast Refresh. */
export const SessionContext = createContext<Session | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession must be used inside a SessionProvider");
  return session;
}
