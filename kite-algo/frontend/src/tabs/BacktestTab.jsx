import { useRef, useState } from "react";
import { runBacktest } from "../api.js";
import EquityChart from "../components/EquityChart.jsx";
import { formatDate, formatMoney, formatPct, formatPrice, signClass } from "../utils/format.js";

// The inputs. Edit these lists to change labels, hints, limits or defaults.
const BASIC_FIELDS = [
  { key: "shortSma", label: "Short SMA", hint: "Fast average, in days.", min: 2, max: 200, initial: "6" },
  { key: "longSma", label: "Long SMA", hint: "Slow average, in days.", min: 3, max: 400, initial: "30" },
  { key: "years", label: "Years of history", hint: "How far back to test (1 to 5).", min: 1, max: 5, initial: "5" },
  { key: "maxStocks", label: "Max Stocks", hint: "How many Nifty 100 stocks to test (1 to 100).", min: 1, max: 100, initial: "100" },
  { key: "startingCapital", label: "Starting capital (₹)", hint: "Money at the start of the test.", min: 10000, max: 1000000000, initial: "1000000" },
  { key: "maxPositions", label: "Max open positions", hint: "Each position gets capital ÷ this.", min: 1, max: 100, initial: "10" },
];
const ADVANCED_FIELDS = [
  { key: "stopLossPct", label: "Stop-loss (%)", hint: "Sell if the price falls this far below your buy price. Empty = no stop-loss.", min: 0.1, max: 50, decimal: true, optional: true, initial: "" },
  { key: "slippagePct", label: "Slippage per side (%)", hint: "How much worse each buy and sell is than the quoted price.", min: 0, max: 2, decimal: true, initial: "0.05" },
];

const SECONDS_PER_STOCK = 0.4; // Kite allows 3 history requests per second

export default function BacktestTab({ onSessionExpired }) {
  const [form, setForm] = useState(() =>
    Object.fromEntries([...BASIC_FIELDS, ...ADVANCED_FIELDS].map((f) => [f.key, f.initial]))
  );
  const [includeCharges, setIncludeCharges] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const expiredRef = useRef(onSessionExpired);
  expiredRef.current = onSessionExpired;

  const estimateSeconds = Math.ceil(((Number(form.maxStocks) || 0) + 1) * SECONDS_PER_STOCK);

  async function handleSubmit(e) {
    e.preventDefault();
    const { values, problem } = validate(form, includeCharges);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setData(null); // drop the previous results so an error never sits above stale data
    setLoading(true);
    try {
      setData(await runBacktest(values));
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

  function renderField(f) {
    return (
      <div className="field" key={f.key}>
        <label className="field-label" htmlFor={`bt-${f.key}`}>
          {f.label}
        </label>
        <input
          id={`bt-${f.key}`}
          type="number"
          inputMode={f.decimal ? "decimal" : "numeric"}
          min={f.min}
          max={f.max}
          step={f.decimal ? "any" : 1}
          value={form[f.key]}
          onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
          aria-describedby={`bt-${f.key}-hint`}
          disabled={loading}
        />
        <span className="field-hint" id={`bt-${f.key}-hint`}>
          {f.hint}
        </span>
      </div>
    );
  }

  return (
    <div className="stack">
      <form className="card panel" onSubmit={handleSubmit} noValidate>
        <h2>SMA crossover backtest</h2>
        <p className="muted">
          Replays the Signals rule on past Nifty 100 prices: buy the day after a bullish crossover, sell the day
          after a bearish one, with Zerodha charges and slippage.
        </p>

        <div className="form-grid">{BASIC_FIELDS.map(renderField)}</div>

        <details className="details advanced">
          <summary>Advanced</summary>
          <div className="form-grid">
            {ADVANCED_FIELDS.map(renderField)}
            <div className="field">
              <span className="field-label">Zerodha charges</span>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={includeCharges}
                  onChange={(e) => setIncludeCharges(e.target.checked)}
                  disabled={loading}
                />
                <span>Include charges</span>
              </label>
              <span className="field-hint">Turn off only to see how much costs matter.</span>
            </div>
          </div>
        </details>

        {error && (
          <div className="alert alert-danger" role="alert">
            {error}
          </div>
        )}

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Running…" : "Run Backtest"}
          </button>
          {loading && (
            <div className="scan-status" role="status">
              <div className="progress" aria-hidden="true" />
              <span>
                Testing up to {form.maxStocks} stocks over {form.years} {Number(form.years) === 1 ? "year" : "years"}. The
                first run downloads prices from Kite, about {estimateSeconds} seconds. Later runs reuse the saved
                prices and finish much faster.
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
const TRADES_SHOWN = 200;

function Results({ data }) {
  const { summary, benchmarks, params, period, universe, trades, costs } = data;
  const [showAll, setShowAll] = useState(false);
  const idx = benchmarks.nifty100;
  const same = benchmarks.same_stocks;
  const shown = showAll ? trades : trades.slice(0, TRADES_SHOWN);
  const skipped = data.signals_skipped;
  const skippedTotal = skipped.no_free_slot + skipped.not_enough_cash;

  return (
    <section aria-label="Backtest results" className="stack">
      <div className="summary">
        <strong>
          {formatDate(period.start)} to {formatDate(period.end)}
        </strong>
        <span className="muted-inline">
          SMA {params.short_sma}/{params.long_sma} · {universe.used} of {universe.requested} stocks ·{" "}
          {formatMoney(params.starting_capital)} in {params.max_positions} slots
          {params.stop_loss_pct ? ` · ${params.stop_loss_pct}% stop` : ""}
        </span>
      </div>

      <div className="alert alert-warning" role="note">
        Survivorship bias: this test uses today's Nifty 100 members. Stocks that dropped out of the index are
        missing, which flatters a long-only test. Compare with "Same stocks, buy and hold" to see how much comes
        from the signal.
      </div>
      {data.market_open && (
        <div className="alert alert-warning" role="note">
          The market is open, so the last day's price is still moving and the final numbers can change by the close.
        </div>
      )}
      {universe.stale && (
        <div className="alert alert-warning" role="note">
          The Nifty 100 list could not be downloaded, so an older saved copy was used.
        </div>
      )}
      {data.notes.map((n) => (
        <div className="alert alert-warning" role="note" key={n}>
          {n}
        </div>
      ))}

      <div className="grid cards">
        <Card
          label="Total return"
          value={formatPct(summary.total_return_pct)}
          tone={signClass(summary.total_return_pct)}
          sub={`${formatMoney(params.starting_capital)} → ${formatMoney(summary.final_value)}${
            summary.cagr_pct !== null ? ` · ${formatPct(summary.cagr_pct)} a year` : ""
          }`}
        />
        <Card
          label="Nifty 100 index"
          value={idx ? formatPct(idx.total_return_pct) : "Not available"}
          tone={idx ? signClass(idx.total_return_pct) : ""}
          sub={idx ? versus(summary.total_return_pct, idx.total_return_pct) : "Index prices missing"}
        />
        <Card
          label="Same stocks, buy and hold"
          value={same ? formatPct(same.total_return_pct) : "Not available"}
          tone={same ? signClass(same.total_return_pct) : ""}
          sub={same ? versus(summary.total_return_pct, same.total_return_pct) : ""}
        />
        <Card
          label="Max drawdown"
          value={formatPct(summary.max_drawdown_pct)}
          tone={signClass(summary.max_drawdown_pct)}
          sub={idx ? `Index: ${formatPct(idx.max_drawdown_pct)}` : "Worst peak-to-trough fall"}
        />
        <Card
          label="Win rate"
          value={summary.win_rate_pct === null ? "n/a" : `${summary.win_rate_pct.toFixed(1)}%`}
          sub={`${summary.wins} wins of ${summary.trades} trades`}
        />
        <Card
          label="Profit factor"
          value={summary.profit_factor === null ? "n/a" : summary.profit_factor.toFixed(2)}
          sub="Gross profit ÷ gross loss"
        />
        <Card
          label="Average win / loss"
          value={`${formatPct(summary.avg_win_pct, 1)} / ${formatPct(summary.avg_loss_pct, 1)}`}
          sub="Per trade, after costs"
        />
        <Card
          label="Average holding"
          value={summary.avg_holding_days === null ? "n/a" : `${summary.avg_holding_days} days`}
          sub="Calendar days per trade"
        />
        <Card
          label="Costs paid"
          value={formatMoney(costs.total)}
          sub={`Charges ${formatMoney(costs.charges)} + slippage ${formatMoney(costs.slippage)}`}
        />
      </div>

      <div className="card chart-card">
        <h3>Equity curve</h3>
        <EquityChart curve={data.equity_curve} />
      </div>

      <h3 className="section-title">Trades ({trades.length})</h3>
      {trades.length === 0 ? (
        <div className="card empty">
          <strong>No trades.</strong>
          <span>No bullish crossover led to a trade in this period. Try a shorter Short SMA or more years.</span>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <caption className="sr-only">Backtest trades, newest entry first</caption>
            <thead>
              <tr>
                <th scope="col">Ticker</th>
                <th scope="col">Entry Date</th>
                <th scope="col" className="num">Entry Price</th>
                <th scope="col">Exit Date</th>
                <th scope="col" className="num">Exit Price</th>
                <th scope="col" className="num">Days Held</th>
                <th scope="col" className="num">P&amp;L (₹)</th>
                <th scope="col" className="num">P&amp;L (%)</th>
                <th scope="col">Exit Reason</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((t) => (
                <tr key={`${t.symbol}-${t.entry_date}`}>
                  <td className="ticker" title={t.company}>{t.symbol}</td>
                  <td>{formatDate(t.entry_date)}</td>
                  <td className="num">{formatPrice(t.entry_price)}</td>
                  <td>{formatDate(t.exit_date)}</td>
                  <td className="num">{formatPrice(t.exit_price)}</td>
                  <td className="num">{t.days_held}</td>
                  <td className={`num ${signClass(t.pnl)}`}>{formatPrice(t.pnl)}</td>
                  <td className={`num ${signClass(t.pnl_pct)}`}>{formatPct(t.pnl_pct)}</td>
                  <td>{REASONS[t.exit_reason] || t.exit_reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {trades.length > TRADES_SHOWN && !showAll && (
        <button className="btn btn-ghost" onClick={() => setShowAll(true)}>
          Show all {trades.length} trades
        </button>
      )}

      <p className="footnote">
        Fills happen at the next day's open. Positions still open on the last day are sold at that day's close ("End of
        test"). Prices exclude dividends for the strategy and both benchmarks.
        {skippedTotal > 0 &&
          ` ${skippedTotal} signals were skipped: ${skipped.no_free_slot} with no free slot, ${skipped.not_enough_cash} that didn't fit the cash available.`}
      </p>

      {data.excluded.length > 0 && (
        <details className="details">
          <summary>
            {data.excluded.length} {data.excluded.length === 1 ? "stock was" : "stocks were"} excluded for suspect data
          </summary>
          <ul>
            {data.excluded.map((s) => (
              <li key={s.symbol}>
                <span className="ticker">{s.symbol}</span>: {s.reason}
              </li>
            ))}
          </ul>
        </details>
      )}
      {data.skipped.length > 0 && (
        <details className="details">
          <summary>
            {data.skipped.length} {data.skipped.length === 1 ? "stock was" : "stocks were"} skipped
          </summary>
          <ul>
            {data.skipped.map((s) => (
              <li key={s.symbol}>
                <span className="ticker">{s.symbol}</span>: {s.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      <details className="details">
        <summary>How to read these results</summary>
        <p>
          The strategy only matters if it beats both benchmarks after costs. If it trails "Same stocks, buy and hold",
          the crossover rule is costing you money compared with simply holding the same shares.
        </p>
        <p>
          A good result on past data does not predict future returns, and trying many SMA lengths on the same years
          will eventually find one that looks good by luck.
        </p>
      </details>
    </section>
  );
}

const REASONS = {
  "bearish crossover": "Bearish crossover",
  "stop-loss": "Stop-loss",
  "end of test": "End of test",
};

function Card({ label, value, sub, tone = "" }) {
  return (
    <div className="card stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${tone}`}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

// "Strategy beat it by 4.2 points" / "lagged it by 3.1 points"
function versus(strategy, other) {
  const diff = strategy - other;
  if (Math.abs(diff) < 0.005) return "Same as the strategy";
  return `Strategy ${diff > 0 ? "beat" : "lagged"} it by ${Math.abs(diff).toFixed(2)} points`;
}

// ---------------------------------------------------------------- helpers ---
function validate(form, includeCharges) {
  const values = { includeCharges };
  for (const f of [...BASIC_FIELDS, ...ADVANCED_FIELDS]) {
    const raw = String(form[f.key]).trim();
    if (raw === "" && f.optional) {
      values[f.key] = null;
      continue;
    }
    const n = Number(raw);
    if (raw === "" || !Number.isFinite(n) || (!f.decimal && !Number.isInteger(n))) {
      return { problem: `${f.label} must be ${f.decimal ? "a number" : "a whole number"}.` };
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
