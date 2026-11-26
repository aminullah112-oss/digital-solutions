import { useRef, useState } from "react";
import { runSmaCrossover } from "../api.js";

// The four inputs. Edit this list to change labels, hints, limits or defaults.
const FIELDS = [
  { key: "shortSma", label: "Short SMA", hint: "Fast average, in days.", min: 2, max: 200, initial: 6 },
  { key: "longSma", label: "Long SMA", hint: "Slow average, in days.", min: 3, max: 400, initial: 30 },
  {
    key: "lookbackDays",
    label: "Lookback Days",
    hint: "Only crossovers from the last N trading days.",
    min: 1,
    max: 250,
    initial: 20,
  },
  { key: "maxStocks", label: "Max Stocks", hint: "How many Nifty 100 stocks to scan (1 to 100).", min: 1, max: 100, initial: 100 },
];

const SECONDS_PER_STOCK = 0.4; // Kite allows 3 history requests per second

export default function SignalsTab({ onSessionExpired }) {
  const [form, setForm] = useState(() => Object.fromEntries(FIELDS.map((f) => [f.key, String(f.initial)])));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const expiredRef = useRef(onSessionExpired);
  expiredRef.current = onSessionExpired;

  const estimateSeconds = Math.ceil((Number(form.maxStocks) || 0) * SECONDS_PER_STOCK);

  async function handleSubmit(e) {
    e.preventDefault();
    const { values, problem } = validate(form);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setData(null); // drop the previous results so an error never sits above stale data
    setLoading(true);
    try {
      setData(await runSmaCrossover(values));
    } catch (err) {
      if (err.status === 401) {
        expiredRef.current();
        return;
      }
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="stack">
      <form className="card panel" onSubmit={handleSubmit} noValidate>
        <h2>Nifty 100 SMA crossover scanner</h2>
        <p className="muted">
          Finds stocks where the short moving average recently crossed the long one, newest first.
        </p>

        <div className="form-grid">
          {FIELDS.map((f) => (
            <div className="field" key={f.key}>
              <label className="field-label" htmlFor={`signals-${f.key}`}>
                {f.label}
              </label>
              <input
                id={`signals-${f.key}`}
                type="number"
                inputMode="numeric"
                min={f.min}
                max={f.max}
                step={1}
                value={form[f.key]}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                aria-describedby={`signals-${f.key}-hint`}
                disabled={loading}
              />
              <span className="field-hint" id={`signals-${f.key}-hint`}>
                {f.hint}
              </span>
            </div>
          ))}
        </div>

        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Scanning…" : "Generate Signals"}
          </button>
          {loading && (
            <div className="scan-status" role="status">
              <div className="progress" aria-hidden="true" />
              <span>
                Scanning up to {form.maxStocks} stocks. Kite allows 3 history requests per second, so this takes
                about {estimateSeconds} seconds.
              </span>
            </div>
          )}
        </div>
      </form>

      {data && <Results data={data} />}
    </div>
  );
}

// ---------------------------------------------------------------- results ---
function Results({ data }) {
  const { params, results, skipped, universe } = data;
  const bullish = results.filter((r) => r.crossover_type === "bullish").length;
  const bearish = results.length - bullish;

  return (
    <section aria-label="Scan results" className="stack">
      <div className="summary">
        <strong>
          {results.length} {results.length === 1 ? "signal" : "signals"}
        </strong>
        <span className="chip chip-bull">{bullish} bullish</span>
        <span className="chip chip-bear">{bearish} bearish</span>
        <span className="muted-inline">
          SMA {params.short_sma}/{params.long_sma} · last {params.lookback_days} trading days · scanned{" "}
          {universe.scanned} of {universe.requested} stocks
        </span>
      </div>

      {data.market_open && (
        <div className="alert alert-warning" role="note">
          The market is open, so today's candle is still forming. A crossover dated today can change before the
          close.
        </div>
      )}
      {universe.stale && (
        <div className="alert alert-warning" role="note">
          The Nifty 100 list could not be downloaded, so an older saved copy was used. Constituents may have
          changed.
        </div>
      )}

      {results.length === 0 ? (
        <div className="card empty">
          <strong>No crossovers found.</strong>
          <span>
            Nothing crossed in the last {params.lookback_days} trading days. Try a larger Lookback Days value.
          </span>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <caption className="sr-only">
              SMA crossover signals, ranked by most recent crossover date
            </caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Ticker</th>
                <th scope="col">Company</th>
                <th scope="col">Crossover Type</th>
                <th scope="col">Crossover Date</th>
                <th scope="col" className="num">
                  Close
                </th>
                <th scope="col" className="num">
                  SMA {params.short_sma}
                </th>
                <th scope="col" className="num">
                  SMA {params.long_sma}
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.symbol}>
                  <td className="rank">{r.rank}</td>
                  <td className="ticker">{r.symbol}</td>
                  <td className="company">{r.company}</td>
                  <td>
                    <TypeBadge type={r.crossover_type} />
                  </td>
                  <td>{formatDate(r.crossover_date)}</td>
                  <td className="num">{formatPrice(r.close)}</td>
                  <td className="num">{formatPrice(r.sma_short)}</td>
                  <td className="num">{formatPrice(r.sma_long)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="footnote">
        Ranked by most recent crossover date. Close and SMA values are from the crossover day. Latest candle:{" "}
        {data.data_as_of ? formatDate(data.data_as_of) : "n/a"}.
      </p>

      {skipped.length > 0 && (
        <details className="details">
          <summary>
            {skipped.length} {skipped.length === 1 ? "stock was" : "stocks were"} skipped
          </summary>
          <ul>
            {skipped.map((s) => (
              <li key={s.symbol}>
                <span className="ticker">{s.symbol}</span>: {s.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      <details className="details">
        <summary>What do these signals mean?</summary>
        <p>
          <strong>Bullish:</strong> the short SMA moved from below the long SMA to above it, so recent prices are
          rising faster than the longer trend. <strong>Bearish:</strong> the opposite.
        </p>
        <p>
          Moving averages lag price, and crossovers often fire falsely when a stock moves sideways. Treat this as
          a shortlist to research, not as a buy or sell instruction.
        </p>
      </details>
    </section>
  );
}

function TypeBadge({ type }) {
  const bullish = type === "bullish";
  return (
    <span className={`badge ${bullish ? "badge-bull" : "badge-bear"}`}>
      <span aria-hidden="true">{bullish ? "▲" : "▼"}</span> {bullish ? "Bullish" : "Bearish"}
    </span>
  );
}

// ---------------------------------------------------------------- helpers ---
function validate(form) {
  const values = {};
  for (const f of FIELDS) {
    const n = Number(form[f.key]);
    if (form[f.key].trim() === "" || !Number.isInteger(n)) {
      return { problem: `${f.label} must be a whole number.` };
    }
    if (n < f.min || n > f.max) {
      return { problem: `${f.label} must be between ${f.min} and ${f.max}.` };
    }
    values[f.key] = n;
  }
  if (values.shortSma >= values.longSma) {
    return { problem: "Short SMA must be smaller than Long SMA." };
  }
  return { values };
}

// "2026-11-25" -> "25 Nov 2026". Parsed by hand so time zones can't shift the day.
function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

function formatPrice(n) {
  return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
