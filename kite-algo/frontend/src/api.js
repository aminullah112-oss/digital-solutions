// Small wrapper around fetch() for talking to the FastAPI backend.
// Every call goes to /api/..., which Vite forwards to the backend.
//
// Note what is NOT here: the access token. The browser never sees it.
// The backend keeps it and uses it for you.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError("Cannot reach the backend. Is it running on port 8000?", 0);
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // Non-JSON response (for example the proxy error page when the backend is down).
  }

  if (!res.ok) {
    throw new ApiError(errorMessage(data, res.status), res.status);
  }
  return data;
}

// FastAPI sends { detail: "text" } for our errors and
// { detail: [ { msg, loc }, ... ] } for validation errors.
function errorMessage(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) return "Please fill in all fields.";
  if (status >= 500) return "Cannot reach the backend. Is it running on port 8000?";
  return `Request failed (${status}).`;
}

export const getAuthStatus = () => request("/api/auth/status");

export const login = ({ apiKey, apiSecret, requestToken }) =>
  request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({
      api_key: apiKey,
      api_secret: apiSecret,
      request_token: requestToken,
    }),
  });

export const logout = () => request("/api/auth/logout", { method: "POST" });

export const getProfile = () => request("/api/profile");

// Scans the Nifty 100 for SMA crossovers. Slow on purpose: Kite allows only
// 3 history requests per second, so 100 stocks take about 40 seconds.
export const runSmaCrossover = ({ shortSma, longSma, lookbackDays, maxStocks }) =>
  request("/api/signals/sma-crossover", {
    method: "POST",
    body: JSON.stringify({
      short_sma: shortSma,
      long_sma: longSma,
      lookback_days: lookbackDays,
      max_stocks: maxStocks,
    }),
  });
