import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { login } from "../api.js";

export default function LoginPage({ initialError = "", onLoggedIn }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [requestToken, setRequestToken] = useState("");
  const [error, setError] = useState(initialError);
  const [submitting, setSubmitting] = useState(false);

  // After you log in on Zerodha's site, Kite redirects back to this page with
  // ?request_token=... in the address bar. Pick it up automatically, then
  // remove it from the URL so it doesn't linger in the browser history.
  useEffect(() => {
    const fromUrl = searchParams.get("request_token");
    if (fromUrl) {
      setRequestToken(fromUrl);
      navigate("/login", { replace: true });
    }
  }, [searchParams, navigate]);

  const kiteLoginUrl = apiKey.trim()
    ? `https://kite.zerodha.com/connect/login?v=3&api_key=${encodeURIComponent(apiKey.trim())}`
    : null;

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const user = await login({
        apiKey: apiKey.trim(),
        apiSecret: apiSecret.trim(),
        requestToken: requestToken.trim(),
      });
      // Don't keep the secret around in memory longer than needed.
      setApiSecret("");
      onLoggedIn(user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.message);
      // A request token can only be used once, so the old one is now useless.
      setRequestToken("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="center-screen">
      <div className="card login-card">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">K</span>
          <span className="brand-name">Kite Algo</span>
        </div>
        <h1>Connect to Zerodha</h1>
        <p className="muted">
          Sign in with your Kite Connect app details. Your access token is created and kept on the
          backend and never shown here.
        </p>

        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="form">
          <label className="field">
            <span className="field-label">API Key</span>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              required
            />
          </label>

          <label className="field">
            <span className="field-label">API Secret</span>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              required
            />
          </label>

          {/* The hint sits outside the <label> so screen readers announce just
              "Request Token" as the name, and the hint as a description. */}
          <div className="field">
            <label className="field-label" htmlFor="request-token">
              Request Token
            </label>
            <input
              id="request-token"
              type="text"
              value={requestToken}
              onChange={(e) => setRequestToken(e.target.value)}
              autoComplete="off"
              spellCheck={false}
              aria-describedby="request-token-hint"
              required
            />
            <span className="field-hint" id="request-token-hint">
              {kiteLoginUrl ? (
                <>
                  <a href={kiteLoginUrl} target="_blank" rel="noopener noreferrer">
                    Open Kite login
                  </a>{" "}
                  to get a new one. It works only once and expires in a few minutes.
                </>
              ) : (
                "Enter your API Key first, then a link to get a request token appears here."
              )}
            </span>
          </div>

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Logging in…" : "Login"}
          </button>
        </form>
      </div>
    </main>
  );
}
