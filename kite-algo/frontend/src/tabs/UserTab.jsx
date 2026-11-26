import { useCallback, useEffect, useRef, useState } from "react";
import { getProfile } from "../api.js";

export default function UserTab({ onSessionExpired }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  // Keep the latest callback in a ref so `load` stays the same function.
  // Otherwise the profile would be re-fetched every time the dashboard re-renders.
  const expiredRef = useRef(onSessionExpired);
  expiredRef.current = onSessionExpired;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setProfile(await getProfile());
    } catch (err) {
      if (err.status === 401) {
        expiredRef.current();
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="grid">
        {["User Name", "User ID", "Products", "Exchanges"].map((label) => (
          <div className="card stat" key={label}>
            <div className="stat-label">{label}</div>
            <div className="skeleton" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        <span>{error}</span>
        <button className="btn btn-ghost" onClick={load}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="grid">
      <Stat label="User Name" value={profile.user_name} />
      <Stat label="User ID" value={profile.user_id} />
      <Chips label="Products" items={profile.products} />
      <Chips label="Exchanges" items={profile.exchanges} />
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value || "—"}</div>
    </div>
  );
}

function Chips({ label, items }) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      {items.length ? (
        <ul className="chips">
          {items.map((item) => (
            <li className="chip" key={item}>
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <div className="stat-value">—</div>
      )}
    </div>
  );
}
