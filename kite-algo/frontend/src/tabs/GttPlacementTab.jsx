import { useAlgo } from "../state/AlgoContext.jsx";
import { formatPrice } from "../utils/format.js";

// Read-only. This tab has no buttons: it only DISPLAYS the state of each current Algo Signal.
// The only action, "Run Live", is on the Algo Signals tab, and it only creates DUMMY records.

// "already_active" -> "Already active", "waiting_for_ltp" -> "Waiting for LTP"
const label = (s) => {
  if (!s) return "—";
  const text = String(s).replace(/_/g, " ").replace(/\bltp\b/gi, "LTP");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

// Colour by meaning: green = done/ready, red = stopped, amber = already covered, blue = planned, grey = waiting.
const TONE = {
  success: "ok", ready: "ok", clear: "ok",
  blocked: "bad", failed: "bad", not_available: "bad", invalid: "bad",
  already_active: "warn",
  planned_after_buy: "info",
  waiting_for_ltp: "muted", waiting: "muted", checking: "muted", not_placed: "muted",
};

function Pill({ value }) {
  if (!value) return <span className="muted-cell">—</span>;
  return <span className={`pill pill-${TONE[value] || "muted"}`}>{label(value)}</span>;
}

const price = (n) => (n === null || n === undefined ? <span className="muted-cell">Unavailable</span> : formatPrice(n));
const dash = (v) => (v === null || v === undefined || v === "" ? <span className="muted-cell">—</span> : v);

export default function GttPlacementTab() {
  const { scannerStatus, scannerError, gttRows, gttError, liveMode, notice } = useAlgo();
  const loading = scannerStatus === "loading";

  return (
    <div className="stack">
      <div>
        <h2>
          GTT Order Placement {liveMode && <span className="live-badge">LIVE: real orders</span>}
        </h2>
        <p className="muted-inline">
          Read-only status from Algo Signals · Qty 1 · Buy GTT at breakout candle low · Stoploss 5% below buy · State from Kite orders, positions,
          holdings, and GTTs
        </p>
      </div>

      {liveMode ? (
        <div className="alert alert-danger" role="note">
          LIVE mode. "Run Live" on the Algo Signals tab shows the real buy GTTs it would place, and places them on Zerodha only after you
          confirm. A stoploss is never placed automatically, so a filled buy has no stoploss until you add one yourself.
        </div>
      ) : (
        <div className="alert alert-warning" role="note">
          Simulation only. "Run Live" on the Algo Signals tab saves dummy records on this computer. No order or GTT is sent to Kite, and
          nothing real is created, changed or cancelled.
        </div>
      )}
      {notice && (
        <div className="alert alert-info" role="status">
          {notice}
        </div>
      )}

      {scannerError && (
        <div className="alert alert-danger" role="alert">
          {scannerError}
        </div>
      )}
      {gttError && (
        <div className="alert alert-danger" role="alert">
          {gttError}
        </div>
      )}

      <h3 className="section-title">Kite GTT Placement</h3>

      {loading && (
        <div className="card empty" role="status">
          <span>Loading scanner cache...</span>
        </div>
      )}
      {!loading && gttRows.length === 0 && (
        <div className="card empty">
          <span>No Algo Signals right now, so there are no GTT candidates.</span>
        </div>
      )}
      {gttRows.length > 0 && (
        <div className="table-wrap">
          <table className="table dense gtt-table">
            <caption className="sr-only">GTT candidates from the current Algo Signals (read-only)</caption>
            <thead>
              <tr>
                <th scope="col" className="num">Rank</th>
                <th scope="col">Symbol</th>
                <th scope="col" className="num">Qty</th>
                <th scope="col" className="num">Buy</th>
                <th scope="col" className="num">Stoploss</th>
                <th scope="col" className="num">Last Price</th>
                <th scope="col">Account State</th>
                <th scope="col">Buy Status</th>
                <th scope="col">Buy Trigger</th>
                <th scope="col">Day Buy Order</th>
                <th scope="col" className="num">Position Qty</th>
                <th scope="col">Stoploss Status</th>
                <th scope="col">Stoploss Trigger</th>
                <th scope="col">Message</th>
              </tr>
            </thead>
            <tbody>
              {gttRows.map((r) => (
                <tr key={r.symbol}>
                  <td className="num rank">{r.rank}</td>
                  <td className="symbol" title={r.companyName}>{r.symbol}</td>
                  <td className="num">{r.quantity}</td>
                  <td className="num">{price(r.buy)}</td>
                  <td className="num">{price(r.stoploss)}</td>
                  <td className="num">{r.lastPrice === null ? <span className="muted-cell">Waiting</span> : formatPrice(r.lastPrice)}</td>
                  <td><Pill value={r.accountState} /></td>
                  <td><Pill value={r.buyStatus} /></td>
                  <td className="mono">{dash(r.buyTrigger)}</td>
                  <td className="mono">{r.dayOrder ? `${r.dayOrder.id} (${r.dayOrder.status})` : dash(null)}</td>
                  <td className="num">{dash(r.positionQty)}</td>
                  <td><Pill value={r.stoplossStatus} /></td>
                  <td className="mono">{dash(r.stoplossTrigger)}</td>
                  <td className="message">{r.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
