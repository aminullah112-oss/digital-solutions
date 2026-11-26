import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getGttState, getOhlcSnapshot, getScannerData, refreshScannerData, runLiveGtt } from "../api.js";
import { scanStocks } from "../lib/breakoutScanner.js";
import { buildCandidates, deriveRows, mergePlacementResults, selectReady, toMap } from "../lib/gtt.js";
import { liveStatusText, useLiveTicks } from "./useLiveTicks.js";

// One shared state for the Algo Signals and GTT Placement tabs:
//   scanner data -> signals (the source of truth) -> live ticks + price snapshot -> GTT rows.
// Both tabs read from here, so there is a single websocket and a single set of signals.
//
// Nothing in this file can place a real order. "Run Live" only asks the backend to create DUMMY records.

const AlgoContext = createContext(null);
export const useAlgo = () => useContext(AlgoContext);

const pricesBySymbol = (prices) => Object.fromEntries(Object.entries(prices || {}).map(([sym, p]) => [sym, p.last_price]));

// `enabled` turns true the first time you open Algo Signals or GTT Placement. Until then nothing is downloaded,
// so the other tabs aren't slowed down (the scanner data and the Signals/Backtest scans share one Kite rate limit).
export function AlgoProvider({ onSessionExpired, enabled, children }) {
  const expiredRef = useRef(onSessionExpired);
  expiredRef.current = onSessionExpired;
  // true when the error was a 401 (we were sent back to the login page)
  const sessionExpired = (err) => {
    if (err && err.status === 401) {
      expiredRef.current();
      return true;
    }
    return false;
  };

  // ---- 1. scanner data, then the scanner (exactly the same function every time)
  const [data, setData] = useState({ status: "loading", error: "", stocks: [], metadata: null });
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    getScannerData()
      .then((payload) => !cancelled && setData({ status: "ready", error: "", stocks: payload.stocks, metadata: payload.metadata }))
      .catch((err) => {
        if (cancelled || sessionExpired(err)) return;
        setData({ status: "error", error: err.message, stocks: [], metadata: null });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  const scan = useMemo(() => scanStocks(data.stocks), [data.stocks]);
  const signals = scan.results; // ranking stays fixed until the scanner runs again
  const symbolsKey = useMemo(() => signals.map((s) => s.symbol).sort().join(","), [signals]);
  const tokens = useMemo(() => signals.map((s) => s.instrumentToken), [signals]);

  // ---- 2. live ticks: only for the stocks the scanner currently returns
  const { prices: tickPrices, status: tickStatus } = useLiveTicks(tokens);

  // ---- 3. price snapshot (the fallback when there is no tick yet)
  const [snapshot, setSnapshot] = useState({});
  const [snapshotKey, setSnapshotKey] = useState(""); // the signal set the latest snapshot attempt was for
  useEffect(() => {
    if (!symbolsKey) {
      setSnapshotKey("");
      return undefined;
    }
    let cancelled = false;
    getOhlcSnapshot(symbolsKey.split(","))
      .then((res) => !cancelled && setSnapshot((prev) => ({ ...prev, ...pricesBySymbol(res.prices) })))
      .catch((err) => !cancelled && sessionExpired(err))
      .finally(() => !cancelled && setSnapshotKey(symbolsKey));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey]);

  // Live price for GTT: websocket tick, else snapshot, else nothing ("Waiting").
  const livePriceFor = useCallback((sig) => tickPrices[sig.instrumentToken] ?? snapshot[sig.symbol] ?? null, [tickPrices, snapshot]);
  // Price shown in Algo Signals: the same, and finally the latest candle's close.
  const currentPriceFor = useCallback((sig) => livePriceFor(sig) ?? sig.currentPrice, [livePriceFor]);

  // The newest values, for code that runs after an await.
  const latest = useRef({});
  latest.current = { tickPrices, snapshot, signals };

  // ---- 4. GTT state (read-only) and the Run Live button (dummy records only)
  const [gttResults, setGttResults] = useState({});
  const [gttChecking, setGttChecking] = useState(false);
  const [gttError, setGttError] = useState("");
  const [running, setRunning] = useState(false);
  const runningRef = useRef(false);
  const requestRef = useRef(0); // the newest request wins; older answers are ignored
  const handledKeyRef = useRef(""); // a signal set that Run Live already checked itself

  // Whenever the set of signals changes, ask the backend (read-only) what state each one is in.
  useEffect(() => {
    if (!symbolsKey) {
      setGttResults({});
      setGttChecking(false);
      return;
    }
    if (runningRef.current || handledKeyRef.current === symbolsKey || snapshotKey !== symbolsKey) return;
    const id = ++requestRef.current;
    setGttChecking(true);
    const { signals: current, tickPrices: ticks, snapshot: snap } = latest.current;
    const candidates = buildCandidates(current, (s) => ticks[s.instrumentToken] ?? snap[s.symbol] ?? null);
    getGttState(candidates)
      .then((res) => id === requestRef.current && (setGttResults(toMap(res.results)), setGttError("")))
      .catch((err) => {
        if (id !== requestRef.current || sessionExpired(err)) return;
        setGttError(`GTT state check failed: ${err.message}`);
      })
      .finally(() => id === requestRef.current && setGttChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey, snapshotKey]);

  const runLive = useCallback(async () => {
    if (runningRef.current) return; // repeated clicks do nothing while a run is in progress
    runningRef.current = true;
    setRunning(true);
    setGttError(""); // 2. clear previous GTT placement errors
    requestRef.current += 1; // forget any state check that is still in flight
    setGttChecking(false);
    let stage = "scanner";
    try {
      // 3. force-refresh the scanner data (fall back to a normal load if there is no refresh endpoint)
      let payload;
      try {
        payload = await refreshScannerData();
      } catch (err) {
        if (err.status !== 404 && err.status !== 405) throw err;
        payload = await getScannerData();
      }
      // 4. rerun the existing scanner, same function and same parameters, and show its result in Algo Signals
      const fresh = scanStocks(payload.stocks);
      handledKeyRef.current = fresh.results.map((s) => s.symbol).sort().join(",");
      setData({ status: "ready", error: "", stocks: payload.stocks, metadata: payload.metadata });
      stage = "gtt";

      // 5. snapshot for the fresh signal symbols
      let snap = {};
      if (fresh.results.length) {
        snap = pricesBySymbol((await getOhlcSnapshot(fresh.results.map((s) => s.symbol))).prices);
        setSnapshot((prev) => ({ ...prev, ...snap }));
      }
      // 6. merge snapshot prices with the websocket ticks (a tick is newer than a snapshot)
      const priceOf = (s) => latest.current.tickPrices[s.instrumentToken] ?? snap[s.symbol] ?? latest.current.snapshot[s.symbol] ?? null;
      // 7. GTT candidates from the fresh signals
      const candidates = buildCandidates(fresh.results, priceOf);
      if (!candidates.length) {
        setGttResults({});
        return;
      }
      // 8. read-only state check
      const state = await getGttState(candidates);
      // 9. only rows the backend calls ready, with buy price, stoploss and a price
      const ready = selectReady(candidates, toMap(state.results));
      // 10. DUMMY records for those rows. Nothing is sent to Kite.
      const placed = ready.length ? (await runLiveGtt(ready)).results : [];
      // 11-12. show placement answers for created rows, and the state answer for every skipped row
      setGttResults(mergePlacementResults(state.results, placed));
    } catch (err) {
      if (sessionExpired(err)) return;
      if (stage === "scanner") setData((d) => ({ ...d, error: err.message }));
      setGttError(err.message);
    } finally {
      runningRef.current = false; // 13.
      setRunning(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const gttRows = useMemo(() => deriveRows(signals, livePriceFor, gttResults, gttChecking), [signals, livePriceFor, gttResults, gttChecking]);

  const value = useMemo(
    () => ({
      scannerStatus: data.status,
      scannerError: data.error,
      metadata: data.metadata,
      signals,
      scannedCount: scan.scanned,
      currentPriceFor,
      liveStatus: liveStatusText(tickStatus, tokens.length),
      running,
      runLive,
      gttRows,
      gttError,
    }),
    [data, signals, scan.scanned, currentPriceFor, tickStatus, tokens.length, running, runLive, gttRows, gttError]
  );

  return <AlgoContext.Provider value={value}>{children}</AlgoContext.Provider>;
}
