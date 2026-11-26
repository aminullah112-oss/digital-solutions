// High-volume breakout and retest scanner. Pure functions: no React, no network.
//
// A stock is a setup when, on some recent day (the "breakout candle"):
//   - it closed up (close > open) on at least 3x its average volume of the previous 20 candles,
//   - it closed above the highest high of the previous 20 candles,
// and afterwards:
//   - price made a higher high than the breakout candle's high (the move continued),
//   - and the latest close is now back within 1% of the breakout candle's midpoint (the retest).

export const PARAMS = Object.freeze({
  volumeLookback: 20, // candles used for the average volume
  volumeMultiplier: 3, // breakout volume must be at least this many times the average
  priceLookback: 20, // candles used for the previous high
  maxBreakoutAge: 20, // the breakout may be at most this many candles old
  midpointTolerancePct: 1, // the latest close must be within this % of the breakout midpoint
});

export const MIN_CANDLES = 25;

// ---------------------------------------------------------------- normalizing ---

// Any date-ish value -> "YYYY-MM-DD" (or null). ISO strings keep their own calendar date,
// so "2026-11-25T00:00:00+05:30" stays 2026-11-25 whatever time zone the browser is in.
export function normalizeDate(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
    if (m) return `${m[1]}-${m[2]}-${m[3]}`;
  }
  let d;
  if (value instanceof Date) d = value;
  else if (typeof value === "number") d = new Date(value < 1e12 ? value * 1000 : value);
  else d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const pick = (obj, ...keys) => {
  for (const k of keys) if (obj[k] !== undefined && obj[k] !== null) return obj[k];
  return undefined;
};

const toNumber = (v) => (v === null || v === undefined || v === "" ? NaN : Number(v));

// One raw candle (an object, or Kite's [date, open, high, low, close, volume] array) -> a clean candle or null.
function normalizeCandle(raw) {
  if (!raw) return null;
  const [date, open, high, low, close, volume] = Array.isArray(raw)
    ? raw
    : [pick(raw, "date", "datetime", "timestamp", "time"), pick(raw, "open", "o"), pick(raw, "high", "h"), pick(raw, "low", "l"), pick(raw, "close", "c"), pick(raw, "volume", "v")];
  const candle = { date: normalizeDate(date), open: toNumber(open), high: toNumber(high), low: toNumber(low), close: toNumber(close), volume: toNumber(volume) };
  const ok = candle.date && [candle.open, candle.high, candle.low, candle.close, candle.volume].every(Number.isFinite);
  return ok ? candle : null;
}

// Dates as YYYY-MM-DD, prices and volume as numbers, oldest first. Unusable candles are dropped.
export function normalizeCandles(rawCandles) {
  return (rawCandles || [])
    .map(normalizeCandle)
    .filter(Boolean)
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

export function normalizeStock(raw) {
  return {
    symbol: String(pick(raw, "symbol", "tradingsymbol") ?? "").toUpperCase(),
    companyName: pick(raw, "company_name", "companyName", "company", "name") ?? "",
    instrumentToken: Number(pick(raw, "instrument_token", "instrumentToken", "token")),
    niftyFlags: pick(raw, "nifty_flags", "niftyFlags") ?? {},
    candles: normalizeCandles(raw.candles),
  };
}

// ------------------------------------------------------------------- scanning ---

const mean = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
const maxOf = (xs) => xs.reduce((a, b) => (b > a ? b : a), -Infinity);

// Scan one stock. Returns its most recent accepted setup, or null.
export function scanStock(stock) {
  const { candles } = stock;
  const n = candles.length;
  if (n < MIN_CANDLES) return null;

  const latest = candles[n - 1];
  const currentPrice = latest.close;
  const preceding = Math.max(PARAMS.volumeLookback, PARAMS.priceLookback); // candles every candidate needs before it
  const earliest = Math.max(preceding, n - 1 - PARAMS.maxBreakoutAge);

  // Start at the second-last candle and walk backward: the first accepted setup is the most recent one.
  for (let i = n - 2; i >= earliest; i--) {
    const c = candles[i];

    // Both lookbacks exclude the candidate itself.
    const avgVolume = mean(candles.slice(i - PARAMS.volumeLookback, i).map((x) => x.volume));
    const prevHigh = maxOf(candles.slice(i - PARAMS.priceLookback, i).map((x) => x.high));

    if (!Number.isFinite(avgVolume) || avgVolume <= 0) continue; // no usable average volume
    if (!(c.close > c.open)) continue;
    if (!(c.volume >= PARAMS.volumeMultiplier * avgVolume)) continue;
    if (!(c.close > prevHigh)) continue;

    // The move must have continued: a higher high than the breakout candle's, somewhere after it.
    const subsequentHigh = maxOf(candles.slice(i + 1).map((x) => x.high));
    if (!(subsequentHigh > c.high)) continue;

    const midpoint = (c.high + c.low) / 2;
    const distanceFromMidpoint = ((currentPrice - midpoint) / midpoint) * 100;
    const daysSince = n - 1 - i;
    if (!(Math.abs(distanceFromMidpoint) <= PARAMS.midpointTolerancePct)) continue;
    if (!(daysSince <= PARAMS.maxBreakoutAge)) continue;

    return {
      symbol: stock.symbol,
      companyName: stock.companyName,
      instrumentToken: stock.instrumentToken,
      currentPrice,
      breakoutDate: c.date,
      bIndex: i,
      daysSince,
      breakoutLow: c.low,
      breakoutHigh: c.high,
      midpoint,
      distanceFromMidpoint,
      volMultiple: c.volume / avgVolume,
      prevHigh,
      maxPriceAfter: subsequentHigh,
      returnFromCloseToSubHigh: ((subsequentHigh - c.close) / c.close) * 100,
      retracementHigh: ((subsequentHigh - currentPrice) / subsequentHigh) * 100,
      candles,
    };
  }
  return null;
}

// Scan every stock from the /api/scanner-data response. Every stock counts as scanned.
// Results: youngest breakout first, then the closest to its midpoint.
export function scanStocks(rawStocks) {
  const stocks = (rawStocks || []).map(normalizeStock);
  const results = [];
  for (const stock of stocks) {
    const setup = scanStock(stock);
    if (setup) results.push(setup);
  }
  results.sort((a, b) => a.daysSince - b.daysSince || Math.abs(a.distanceFromMidpoint) - Math.abs(b.distanceFromMidpoint));
  return { results, scanned: stocks.length };
}
