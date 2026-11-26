import { useState } from "react";
import LiveConfirmDialog from "../components/LiveConfirmDialog.jsx";
import { useAlgo } from "../state/AlgoContext.jsx";
import { formatDate, formatPct, formatPrice, signClass } from "../utils/format.js";

export default function AlgoSignalsTab() {
  const { scannerStatus, scannerError, signals, scannedCount, currentPriceFor, liveStatus, running, runLive, gttError, liveMode, pendingLive, placing, confirmLive, cancelLive, notice } = useAlgo();
  const [selected, setSelected] = useState(null);

  const loading = scannerStatus === "loading";
  const failed = scannerStatus === "error";

  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h2>
            High-volume breakout and retest setups{" "}
            {liveMode && <span className="live-badge">LIVE: real orders</span>}
          </h2>
          <p className="muted-inline">
            A green candle on at least 3x its 20-candle average volume, closing above the 20-candle high, followed by a higher high, and now back
            within 1% of the breakout candle's midpoint. Breakouts up to 20 candles old.
          </p>
        </div>
        <div className="run-box">
          <button
            type="button"
            className="btn btn-primary"
            onClick={runLive}
            disabled={running || loading || Boolean(pendingLive) || placing}
            title={
              liveMode
                ? "LIVE: finds the setups and shows the real GTT orders it would place. Nothing is placed until you confirm."
                : "Simulation only: creates dummy records on this computer. Nothing is sent to Kite."
            }
          >
            {running ? "Running..." : "Run Live"}
          </button>
          {liveMode ? (
            <span className="live-note">LIVE: real GTT buy orders, placed only after you confirm</span>
          ) : (
            <span className="dummy-note">Simulation only: dummy records, nothing is sent to Kite</span>
          )}
        </div>
      </div>

      <div className="summary-bar" aria-live="polite">
        <span>
          <strong>{loading ? "…" : signals.length}</strong> triggered breakouts
        </span>
        <span>
          <strong>{loading ? "…" : scannedCount}</strong> stocks scanned
        </span>
        <span className="live-status">{liveStatus}</span>
      </div>

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
      {notice && (
        <div className="alert alert-info" role="status">
          {notice}
        </div>
      )}

      <h3 className="section-title">Triggered Breakouts</h3>

      {loading && (
        <div className="card empty" role="status">
          <span>Loading scanner cache...</span>
        </div>
      )}
      {!loading && !failed && signals.length === 0 && (
        <div className="card empty">
          <span>No breakout retest setups match the current parameters.</span>
        </div>
      )}
      {signals.length > 0 && (
        <div className="table-wrap">
          <table className="table dense algo-table">
            <caption className="sr-only">Triggered breakouts, youngest first, then closest to the midpoint</caption>
            <thead>
              <tr>
                <th scope="col" className="num">Rank</th>
                <th scope="col">Symbol</th>
                <th scope="col" className="num">Current Price</th>
                <th scope="col">Breakout Date</th>
                <th scope="col" className="num">Age</th>
                <th scope="col" className="num">Breakout Vol</th>
                <th scope="col" className="num">Retest Distance</th>
                <th scope="col" className="num">Peak Gains</th>
                <th scope="col" className="num">Retracement</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((s, i) => (
                <tr
                  key={s.symbol}
                  className={selected === s.symbol ? "selected" : ""}
                  aria-current={selected === s.symbol ? "true" : undefined}
                  tabIndex={0}
                  onClick={() => setSelected(s.symbol)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelected(s.symbol);
                    }
                  }}
                >
                  <td className="num rank">{i + 1}</td>
                  <td className="symbol" title={s.companyName}>{s.symbol}</td>
                  <td className="num">{formatPrice(currentPriceFor(s))}</td>
                  <td>{formatDate(s.breakoutDate)}</td>
                  <td className="num">{s.daysSince}</td>
                  <td className="num">{s.volMultiple.toFixed(2)}x</td>
                  <td className={`num ${signClass(s.distanceFromMidpoint)}`}>{formatPct(s.distanceFromMidpoint)}</td>
                  <td className={`num ${signClass(s.returnFromCloseToSubHigh)}`}>{formatPct(s.returnFromCloseToSubHigh)}</td>
                  <td className={`num ${signClass(s.retracementHigh)}`}>{formatPct(s.retracementHigh)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pendingLive && <LiveConfirmDialog pending={pendingLive} placing={placing} onConfirm={confirmLive} onCancel={cancelLive} />}
    </div>
  );
}
