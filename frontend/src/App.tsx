import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Architecture } from "./components/Architecture";
import { Chat } from "./components/Chat";
import { Landing } from "./components/Landing";
import { Login } from "./components/Login";
import { LoginRoute, RedirectIfSignedIn, RequireAuth } from "./components/RouteGuards";
import { SessionProvider } from "./session";

/* Route names avoid /chat, /conversations and /cvs on purpose: CloudFront routes
   those paths to the Lambda proxy, so a page there would never reach the SPA.
   Everything else falls through to index.html (see the stack's error_responses),
   which is what makes these deep links work on a refresh. */

export default function App() {
  return (
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route
            path="/"
            element={
              <RedirectIfSignedIn>
                <Landing />
              </RedirectIfSignedIn>
            }
          />
          <Route
            path="/login"
            element={
              <LoginRoute>
                <Login />
              </LoginRoute>
            }
          />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <Chat />
              </RequireAuth>
            }
          />
          {/* Documentation, not data: no guard, so it reads the same signed in
              or out and can be linked to from the public landing page. */}
          <Route path="/architecture" element={<Architecture />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  );
}
