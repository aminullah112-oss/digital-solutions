import { useRef, useState } from "react";
import { runBacktest, runMomentum } from "../api.js";
import EquityChart from "../components/EquityChart.jsx";
import { formatDate, formatMoney, formatPct, formatPrice, signClass } from "../utils/format.js";

// ------------------------------------------------------------------ inputs ---
// Every input lives in these lists. Edit them to change labels, hints, limits or defaults.
const F = {
  shortSma: { key: "shortSma", label: "Short SMA", hint: "Fast average, in days.", min: 2, max: 200, initial: "6" },
  longSma: { key: "longSma", label: "Long SMA", hint: "Slow average, in days.", min: 3, max: 400, initial: "30" },
  maxPositions: { key: "maxPositions", label: "Max open positions", hint: "Each position gets capital ÷ this.", min: 1, max: 100, initial: "10" },
  lookbackDays: { key: "lookbackDays", label: "Lookback (trading days)", hint: "How far back to measure each stock's return. 252 is about a year.", min: 20, max: 500, initial: "252" },
  skipDays: { key: "skipDays", label: "Skip latest (trading days)", hint: "Ignore the most recent days when ranking. 21 is about a month.", min: 0, max: 60, initial: "21" },
  topN: { key: "topN", label: "Stocks to hold", hint: "Hold this many top-ranked stocks, equal money in each.", min: 1, max: 50, initial: "10" },
  years: { key: "years", label: "Years of history", hint: "How far back to test (1 to 5).", min: 1, max: 5, initial: "5" },
  maxStocks: { key: "maxStocks", label: "Max Stocks", hint: "How many Nifty 100 stocks to test (1 to 100).", min: 1, max: 100, initial: "100" },
  startingCapital: { key: "startingCapital", label: "Starting capital (₹)", hint: "Money at the start of the test.", min: 10000, max: 1000000000, initial: "1000000" },
  keepRank: { key: "keepRank", label: "Keep until rank", hint: "A holding is sold only when it falls below this rank. Empty = twice the stocks held.", min: 1, max: 100, optional: true, initial: "" },
  stopLossPct: { key: "stopLossPct", label: "Stop-loss (%)", hint: "Sell if the price falls this far below your buy price. Empty = no stop-loss.", min: 0.1, max: 50, decimal: true, optional: true, initial: "" },
  slippagePct: { key: "slippagePct", label: "Slippage per side (%)", hint: "How much worse each buy and sell is than the quoted price.", min: 0, max: 2, decimal: true, initial: "0.05" },
  holdoutPct: { key: "holdoutPct", label: "Hold out the last (%)", hint: "Reported separately so you can judge on days the strategy wasn't tuned on. 0 = off.", min: 0, max: 80, initial: "40" },
  regimeSma: { key: "regimeSma", label: "Index average (days)", hint: "The Nifty 100 must close above this many days' average.", min: 20, max: 400, initial: "200" },
};

const STRATEGIES = {
  sma_crossover: {
    label: "SMA crossover",
    blurb: "Buys the day after the short average crosses above the long one, sells the day after it crosses below.",
    basic: [F.shortSma, F.longSma, F.years, F.maxStocks, F.startingCapital, F.maxPositions],
    advanced: [F.stopLossPct, F.slippagePct, F.holdoutPct],
    secondsPerStock: 0.4, // Kite allows 3 history requests per second
    run: runBacktest,
  },
  momentum: {
    label: "Momentum rotation",
    blurb: "Once a month, holds the stocks that rose the most (skipping the latest weeks) and sells any that drop out of the ranking.",
    basic: [F.lookbackDays, F.skipDays, F.topN, F.years, F.maxStocks, F.startingCapital],
    advanced: [F.keepRank, F.stopLossPct, F.slippagePct, F.holdoutPct],
    secondsPerStock: 0.8, // needs about a year more history, so two requests per stock the first time
    run: runMomentum,
  },
};

const ALL_FIELDS = Object.values(F);

export default function BacktestTab({ onSessionExpired }) {
  const [strategy, setStrategy] = useState("sma_crossover");
  const [form, setForm] = useState(() => Object.fromEntries(ALL_FIELDS.map((f) => [f.key, f.initial])));
  const [includeCharges, setIncludeCharges] = useState(true);
  const [regimeFilter, setRegimeFilter] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const expiredRef = useRef(onSessionExpired);
  expiredRef.current = onSessionExpired;

  const spec = STRATEGIES[strategy];
  const estimateSeconds = Math.ceil(((Number(form.maxStocks) || 0) + 1) * spec.secondsPerStock);

  async function handleSubmit(e) {
    e.preventDefault();
    const { values, problem } = validate(strategy, form, includeCharges, regimeFilter);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setData(null); // drop the previous results so an error never sits above stale data
    setLoading(true);
    try {
      setData(await spec.run(values));
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
        <h2>Backtest</h2>
        <p className="muted">Replays a strategy on past Nifty 100 prices, with Zerodha charges and slippage, next to two benchmarks.</p>

        <div className="field strategy-field">
          <label className="field-label" htmlFor="bt-strategy">
            Strategy
          </label>
          <select id="bt-strategy" value={strategy} onChange={(e) => setStrategy(e.target.value)} aria-describedby="bt-strategy-hint" disabled={loading}>
            {Object.entries(STRATEGIES).map(([id, s]) => (
              <option key={id} value={id}>
                {s.label}
              </option>
            ))}
          </select>
          <span className="field-hint" id="bt-strategy-hint">
            {spec.blurb}
          </span>
        </div>

        <div className="form-grid">{spec.basic.map(renderField)}</div>

        <details className="details advanced">
          <summary>Advanced</summary>
          <div className="form-grid">
            {spec.advanced.map(renderField)}
            <div className="field">
              <span className="field-label">Zerodha charges</span>
              <label className="checkbox-field">
                <input type="checkbox" checked={includeCharges} onChange={(e) => setIncludeCharges(e.target.checked)} disabled={loading} />
                <span>Include charges</span>
              </label>
              <span className="field-hint">Turn off only to see how much costs matter.</span>
            </div>
            <div className="field">
              <span className="field-label">Regime filter</span>
              <label className="checkbox-field">
                <input type="checkbox" checked={regimeFilter} onChange={(e) => setRegimeFilter(e.target.checked)} disabled={loading} />
                <span>Only trade in an uptrend</span>
              </label>
              <span className="field-hint">
                {strategy === "momentum"
                  ? "When the Nifty 100 is below its average at a rebalance, sell everything and wait in cash."
                  : "Skip new buys while the Nifty 100 is below its average. Open positions still exit normally."}
              </span>
            </div>
            {regimeFilter && renderField(F.regimeSma)}
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
                Testing up to {form.maxStocks} stocks over {form.years} {Number(form.years) === 1 ? "year" : "years"}. The first run
                downloads prices from Kite, about {estimateSeconds} seconds. Later runs reuse the saved prices and finish much faster.
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

const REASONS = {
  "bearish crossover": "Bearish crossover",
  "rank dropped": "Dropped out of ranking",
  "regime off": "Regime filter off",
  "stop-loss": "Stop-loss",
  "end of test": "End of test",
};

function describe(data) {
  const p = data.params;
  const rules =
    data.strategy === "momentum"
      ? `Momentum: top ${p.top_n} by ${p.lookback_days}-day return, skipping ${p.skip_days} · ${data.summary.rebalances} rebalances`
      : `SMA ${p.short_sma}/${p.long_sma} · ${formatMoney(p.starting_capital)} in ${p.max_positions} slots`;
  return `${rules} · ${data.universe.used} of ${data.universe.requested} stocks${p.stop_loss_pct ? ` · ${p.stop_loss_pct}% stop` : ""}${
    p.regime_filter ? ` · regime filter ${p.regime_sma}d` : ""
  }`;
}

function Results({ data }) {
  const { summary, benchmarks, params, period, universe, trades, costs } = data;
  const [showAll, setShowAll] = useState(false);
  const idx = benchmarks.nifty100;
  const same = benchmarks.same_stocks;
  const shown = showAll ? trades : trades.slice(0, TRADES_SHOWN);
  const skipped = data.signals_skipped;
  const skippedTotal = skipped.no_free_slot + skipped.not_enough_cash;
  const isMomentum = data.strategy === "momentum";

  return (
    <section aria-label="Backtest results" className="stack">
      <div className="summary">
        <strong>
          {formatDate(period.start)} to {formatDate(period.end)}
        </strong>
        <span className="muted-inline">{describe(data)}</span>
      </div>

      <div className="alert alert-warning" role="note">
        Survivorship bias: this test uses today's Nifty 100 members. Stocks that dropped out of the index are
        missing, which flatters a long-only test, and momentum most of all. Compare with "Same stocks, buy and hold" to see
        how much comes from the strategy.
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

      {data.segments && <Holdout segments={data.segments} />}

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
        <EquityChart curve={data.equity_curve} splitDate={data.segments?.split_date} />
        {data.segments && <p className="footnote chart-note">The shaded part is the held-out period.</p>}
      </div>

      <h3 className="section-title">Trades ({trades.length})</h3>
      {trades.length === 0 ? (
        <div className="card empty">
          <strong>No trades.</strong>
          <span>The strategy never bought anything in this period. Try more years or different settings.</span>
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
          ` ${skippedTotal} buys were skipped: ${skipped.no_free_slot} with no free slot, ${skipped.not_enough_cash} that didn't fit the cash available.`}
        {skipped.regime_off > 0 &&
          (isMomentum
            ? ` The Nifty 100 was below its ${params.regime_sma}-day average at ${skipped.regime_off} monthly rebalances, so the portfolio sat in cash.`
            : ` ${skipped.regime_off} signals were skipped because the Nifty 100 was below its ${params.regime_sma}-day average.`)}
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
          The strategy only matters if it beats both benchmarks after costs, on the held-out period. If it trails "Same stocks,
          buy and hold", the rules are costing you money compared with simply holding the same shares.
        </p>
        <p>
          Change settings and re-run until the held-out numbers look good, and that period stops being held out: you will have
          tuned to it. Pick your settings first, look once, and treat anything else as a new test on new data.
        </p>
      </details>
    </section>
  );
}

// The held-out check: the same numbers for the first part and the last part of the period.
function Holdout({ segments }) {
  const { in_sample: ins, out_of_sample: oos } = segments;
  // [label, how to read the value, whether to color it green/red by sign]
  const rows = [
    ["Period", (s) => `${formatDate(s.period.start)} to ${formatDate(s.period.end)}`, false],
    ["Strategy return", (s) => pct(s.strategy?.total_return_pct), true],
    ["Nifty 100 index return", (s) => pct(s.nifty100?.total_return_pct), true],
    ["Same stocks, buy and hold", (s) => pct(s.same_stocks?.total_return_pct), true],
    ["Strategy max drawdown", (s) => pct(s.strategy?.max_drawdown_pct), true],
    ["Trades closed", (s) => String(s.trades.trades), false],
    ["Win rate", (s) => (s.trades.win_rate_pct === null ? "n/a" : `${s.trades.win_rate_pct.toFixed(1)}%`), false],
  ];
  const verdict = (s) =>
    ["nifty100", "same_stocks"]
      .filter((k) => s[k])
      .map((k) => {
        const diff = s.strategy.total_return_pct - s[k].total_return_pct;
        return `${diff >= 0 ? "ahead of" : "behind"} ${k === "nifty100" ? "the Nifty 100" : "the same stocks held"} by ${Math.abs(diff).toFixed(1)} points`;
      })
      .join(" and ");

  return (
    <div className="card holdout">
      <h3>Held-out check</h3>
      <p className="muted-inline">
        The last {segments.holdout_pct}% of the period is reported separately. Judge the strategy on the right-hand column.
      </p>
      <div className="table-wrap flat">
        <table className="table">
          <caption className="sr-only">In-sample and held-out results</caption>
          <thead>
            <tr>
              <th scope="col"></th>
              <th scope="col">First part (in-sample)</th>
              <th scope="col">Last part (held out)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, get, colored]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td className={colored ? signed(get(ins)) : ""}>{get(ins)}</td>
                <td className={colored ? signed(get(oos)) : ""}>{get(oos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {oos.strategy && (
        <p className="holdout-verdict">
          Held out: the strategy finished {verdict(oos) || "with no benchmark to compare"}.
        </p>
      )}
    </div>
  );
}

const pct = (n) => (n === null || n === undefined ? "n/a" : formatPct(n));
const signed = (text) => (text.startsWith("+") ? "pos" : text.startsWith("-") ? "neg" : "");

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
function validate(strategy, form, includeCharges, regimeFilter) {
  const spec = STRATEGIES[strategy];
  const fields = [...spec.basic, ...spec.advanced, ...(regimeFilter ? [F.regimeSma] : [])];
  const values = { includeCharges, regimeFilter };
  for (const f of fields) {
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
  if (!regimeFilter) values.regimeSma = Number(F.regimeSma.initial);
  if (strategy === "sma_crossover" && values.shortSma >= values.longSma) {
    return { problem: "Short SMA must be smaller than Long SMA." };
  }
  if (strategy === "momentum") {
    if (values.skipDays >= values.lookbackDays) return { problem: "Skip latest must be smaller than the lookback." };
    if (values.keepRank !== null && values.keepRank < values.topN) {
      return { problem: "Keep until rank must be at least the number of stocks held." };
    }
  }
  return { values };
}
