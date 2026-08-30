import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserPool,
} from "amazon-cognito-identity-js";

// Injected at build time by `make frontend-build` from the stack outputs. Absent
// locally, where auth is off — same rule as backend/app/auth.py.
const USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID ?? "";
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID ?? "";

/** describe-stacks prints "None" for a missing output and Vite bakes it in
 *  verbatim, so treat that as unset. */
function configured(value: string): boolean {
  return value !== "" && value !== "None" && value !== "undefined";
}

export const authEnabled = configured(USER_POOL_ID) && configured(CLIENT_ID);

// CognitoUserPool throws on a malformed id; caught so a misconfigured build
// fails at the login form rather than at import time, with a blank page.
const pool = (() => {
  if (!authEnabled) return null;
  try {
    return new CognitoUserPool({ UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID });
  } catch (err) {
    console.error("Cognito is misconfigured for this build:", err);
    return null;
  }
})();

/** Access token for the current session, refreshing it if it has expired.
 *  Resolves to null when nobody is signed in (or auth is off). */
export function getAccessToken(): Promise<string | null> {
  if (!pool) return Promise.resolve(null);
  const user = pool.getCurrentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve) => {
    // getSession swaps the stored refresh token for fresh tokens when needed,
    // which is what keeps a session alive across reloads for ~30 days.
    user.getSession((err: Error | null, session: { getAccessToken(): { getJwtToken(): string } } | null) => {
      if (err || !session) {
        resolve(null);
        return;
      }
      resolve(session.getAccessToken().getJwtToken());
    });
  });
}

export function signIn(username: string, password: string): Promise<void> {
  if (!pool) return Promise.reject(new Error("Authentication is not configured."));
  const user = new CognitoUser({ Username: username, Pool: pool });
  return new Promise((resolve, reject) => {
    user.authenticateUser(
      new AuthenticationDetails({ Username: username, Password: password }),
      {
        onSuccess: () => resolve(),
        onFailure: (err: { message?: string }) =>
          // Cognito is deliberately vague here (prevent_user_existence_errors),
          // so pass its wording through rather than inventing a better one.
          reject(new Error(err?.message ?? "Could not sign in.")),
        // Only reachable for an account created without --permanent.
        newPasswordRequired: () =>
          reject(
            new Error(
              "This account still needs its first password set. Run `make cognito-user` again.",
            ),
          ),
      },
    );
  });
}

export function signOut(): void {
  pool?.getCurrentUser()?.signOut();
}

export function currentUsername(): string | null {
  return pool?.getCurrentUser()?.getUsername() ?? null;
}

// Set by App so an expired session drops straight to the login screen instead of
// surfacing a 401 as a chat error.
let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

export function notifyUnauthorized(): void {
  onUnauthorized();
}
