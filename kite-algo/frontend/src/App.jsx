import { useCallback, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getAuthStatus } from "./api.js";
import LoginPage from "./pages/LoginPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

// auth.state is one of: "loading" | "in" | "out"
export default function App() {
  const [auth, setAuth] = useState({ state: "loading", user: null, error: "" });

  // On first load, ask the backend if a saved session is still valid.
  // This is what keeps you logged in across refreshes and backend reloads.
  useEffect(() => {
    let cancelled = false;
    getAuthStatus()
      .then((s) => {
        if (cancelled) return;
        setAuth(
          s.logged_in
            ? { state: "in", user: { id: s.user_id, name: s.user_name }, error: "" }
            : {
                state: "out",
                user: null,
                error: s.reason === "expired" ? "Your session expired. Please log in again." : "",
              }
        );
      })
      .catch((e) => {
        if (!cancelled) setAuth({ state: "out", user: null, error: e.message });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleLoggedIn = useCallback((user) => {
    setAuth({ state: "in", user: { id: user.user_id, name: user.user_name }, error: "" });
  }, []);

  const handleLoggedOut = useCallback((error = "") => {
    setAuth({ state: "out", user: null, error });
  }, []);

  if (auth.state === "loading") {
    return (
      <div className="center-screen">
        <div className="spinner" role="status" aria-label="Loading" />
      </div>
    );
  }

  const loggedIn = auth.state === "in";

  return (
    <Routes>
      <Route
        path="/login"
        element={
          loggedIn ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <LoginPage initialError={auth.error} onLoggedIn={handleLoggedIn} />
          )
        }
      />
      <Route
        path="/dashboard"
        element={
          loggedIn ? (
            <DashboardPage user={auth.user} onLoggedOut={handleLoggedOut} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to={loggedIn ? "/dashboard" : "/login"} replace />} />
    </Routes>
  );
}
