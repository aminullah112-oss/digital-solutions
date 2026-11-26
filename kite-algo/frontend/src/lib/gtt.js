// GTT Placement helpers. Pure functions: no React, no network.
//
// Algo Signals is the source of truth. GTT candidates are derived from the current signals,
// and the GTT table only DISPLAYS state and results. The backend decides what is allowed,
// and it only ever writes dummy records: nothing here can place a real order.

export const QUANTITY = 1;
export const STOPLOSS_FACTOR = 0.95; // stoploss is 5% below the buy price

export const MESSAGES = {
  ready: "Ready for buy GTT placement.",
  waiting: "Waiting for LTP.",
  noBuyPrice: "Buy price is not available for this row.",
};

const isPrice = (n) => typeof n === "number" && Number.isFinite(n) && n > 0;

// The candidate sent to the backend. The buy price is the breakout candle's LOW (never the LTP).
export function buildCandidate(signal, lastPrice) {
  const buy = isPrice(signal.breakoutLow) ? signal.breakoutLow : null;
  return {
    symbol: signal.symbol,
    quantity: QUANTITY,
    buy_price: buy,
    stoploss: buy === null ? null : buy * STOPLOSS_FACTOR, // for display; the server recomputes it with exact decimals
    last_price: isPrice(lastPrice) ? lastPrice : null,
  };
}

export function buildCandidates(signals, lastPriceFor) {
  return signals.map((s) => buildCandidate(s, lastPriceFor(s)));
}

// Which candidates may be sent to the dummy-creation endpoint?
// Only rows with a buy price, a stoploss and a live/snapshot price, that the backend itself called "ready".
// Anything blocked or already active is left out. (The backend repeats every check anyway.)
const SKIP_STATES = new Set(["blocked", "already_active", "position_exists", "day_buy_order_exists"]);

export function selectReady(candidates, stateBySymbol) {
  return candidates.filter((c) => {
    const state = stateBySymbol[c.symbol];
    if (!state) return false;
    if (SKIP_STATES.has(state.buy_status) || SKIP_STATES.has(state.account_state)) return false;
    return isPrice(c.buy_price) && isPrice(c.stoploss) && isPrice(c.last_price) && state.buy_status === "ready";
  });
}

export const toMap = (results) => Object.fromEntries((results || []).map((r) => [r.symbol, r]));

// One table row per CURRENT signal, in the signals' own order. A stock that leaves Algo Signals leaves this table.
// `results` is the backend's latest answer per symbol; `checking` marks rows still waiting for one.
export function deriveRows(signals, lastPriceFor, results, checking) {
  return signals.map((signal, i) => {
    const lastPrice = lastPriceFor(signal);
    const cand = buildCandidate(signal, lastPrice);
    const r = results[signal.symbol];
    const row = {
      rank: i + 1,
      symbol: signal.symbol,
      companyName: signal.companyName,
      quantity: QUANTITY,
      buy: cand.buy_price,
      stoploss: cand.stoploss,
      lastPrice: isPrice(lastPrice) ? lastPrice : null, // the live/snapshot price, whatever the backend saw when it answered
      accountState: "",
      buyStatus: "not_placed",
      buyTrigger: null,
      dayOrder: null,
      positionQty: null,
      stoplossStatus: "not_placed",
      stoplossTrigger: null,
      message: "",
    };

    if (r) {
      return {
        ...row,
        buy: r.buy_price ?? row.buy,
        stoploss: r.stoploss ?? row.stoploss,
        accountState: r.account_state,
        buyStatus: r.buy_status,
        buyTrigger: r.buy_trigger_id ?? r.active_buy_trigger_id ?? null,
        dayOrder: r.day_buy_order_id ? { id: r.day_buy_order_id, status: r.day_buy_order_status } : null,
        positionQty: r.position_quantity,
        stoplossStatus: r.stoploss_status,
        stoplossTrigger: r.stoploss_trigger_id ?? r.active_stoploss_trigger_id ?? null,
        message: r.message,
      };
    }
    if (cand.buy_price === null) {
      return { ...row, accountState: "invalid", buyStatus: "not_available", stoplossStatus: "not_available", message: MESSAGES.noBuyPrice };
    }
    if (checking) return { ...row, accountState: "checking", buyStatus: "checking", stoplossStatus: "checking" };
    if (!isPrice(lastPrice)) return { ...row, accountState: "waiting", buyStatus: "waiting_for_ltp", stoplossStatus: "waiting_for_ltp", message: MESSAGES.waiting };
    return row;
  });
}

// Replace each result's last price with the live one for display (the backend's value was a snapshot in time).
export function mergePlacementResults(stateResults, placedResults) {
  const merged = { ...toMap(stateResults) };
  for (const r of placedResults || []) merged[r.symbol] = r; // a placement answer replaces the state answer
  return merged;
}

// What the confirmation dialog shows: how many orders and what they add up to (buy price x quantity).
export function summarizeLive(rows) {
  const cents = rows.reduce((sum, r) => sum + Math.round(r.buy_price * 100) * r.quantity, 0);
  return { count: rows.length, total: cents / 100 };
}
