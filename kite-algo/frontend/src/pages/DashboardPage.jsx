import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { logout } from "../api.js";
import Tabs from "../components/Tabs.jsx";
import { AlgoProvider } from "../state/AlgoContext.jsx";
import { TABS } from "../tabs/index.js";

export default function DashboardPage({ user, onLoggedOut }) {
  const navigate = useNavigate();
  const [activeId, setActiveId] = useState(TABS[0].id);
  const [loggingOut, setLoggingOut] = useState(false);
  // Load the Algo Signals data the first time one of its two tabs is opened, and keep it afterwards.
  const algoOpened = useRef(false);
  if (activeId === "algo-signals" || activeId === "gtt-placement") algoOpened.current = true;

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      onLoggedOut();
      navigate("/login", { replace: true });
    }
  }

  // Tabs call this when the backend says the session is gone (HTTP 401).
  function handleSessionExpired() {
    onLoggedOut("Your session expired. Please log in again.");
    navigate("/login", { replace: true });
  }

  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">K</span>
          <span className="brand-name">Kite Algo</span>
        </div>
        <div className="topbar-right">
          <span className="user-chip" title={user?.id || ""}>
            {user?.name || user?.id || "Signed in"}
          </span>
          <button className="btn btn-ghost" onClick={handleLogout} disabled={loggingOut}>
            {loggingOut ? "Logging out…" : "Logout"}
          </button>
        </div>
      </header>

      <main className="content">
        <AlgoProvider onSessionExpired={handleSessionExpired} enabled={algoOpened.current}>
        <Tabs tabs={TABS} activeId={activeId} onChange={setActiveId} />
        {/* Every tab stays mounted and the inactive ones are just hidden, so
            switching tabs never throws away results (e.g. a finished scan). */}
        {TABS.map(({ id, component: TabComponent }) => (
          <section
            key={id}
            className="tab-panel"
            role="tabpanel"
            id={`panel-${id}`}
            aria-labelledby={`tab-${id}`}
            hidden={id !== activeId}
          >
            <TabComponent onSessionExpired={handleSessionExpired} />
          </section>
        ))}
        </AlgoProvider>
      </main>
    </div>
  );
}
