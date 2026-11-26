// Run with:  npm test
// Every expected number is worked out by hand in the comments.
//
// Baseline candle: open 100, high 101, low 99, close 100.5, volume 1000. It never triggers (its close is
// below the previous high), so the tests place single breakout candles into a flat baseline.
import assert from "node:assert/strict";
import test from "node:test";
import { MIN_CANDLES, PARAMS, normalizeCandles, normalizeDate, normalizeStock, scanStock, scanStocks } from "./breakoutScanner.js";

const date = (i) => new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10); // 2026-01-01, 02, ...
const BASE = { open: 100, high: 101, low: 99, close: 100.5, volume: 1000 };

// n candles of baseline, with `patches` {index: {field: value}} applied.
function candles(n, patches = {}, base = BASE) {
  return Array.from({ length: n }, (_, i) => ({ date: date(i), ...base, ...(patches[i] || {}) }));
}
const stock = (cs, symbol = "AAA") => ({ symbol, companyName: `${symbol} Ltd.`, instrumentToken: 111, niftyFlags: {}, candles: cs });

// The standard setup, n = 30: breakout candle at index 25 (age 4), midpoint 103.5, latest close 103.5.
const BREAKOUT = { open: 100, high: 108, low: 99, close: 107, volume: 3000 }; // 3.0x the average of 1000, close above the prior high of 101
const AFTER = { 26: { high: 112, close: 110 }, 27: { high: 109, close: 106 }, 28: { high: 106, close: 104 }, 29: { open: 104, high: 105, low: 103, close: 103.5 } };
const standard = (extra = {}) => candles(30, { 25: BREAKOUT, ...AFTER, ...extra });

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} is not ${b}`);

// ---------------------------------------------------------------- the example ---
test("the standard setup: every field, worked out by hand", () => {
  const r = scanStock(stock(standard()));
  assert.ok(r, "should be accepted");
  assert.equal(r.symbol, "AAA");
  assert.equal(r.companyName, "AAA Ltd.");
  assert.equal(r.bIndex, 25);
  assert.equal(r.daysSince, 4); // candles after index 25: 26, 27, 28, 29
  assert.equal(r.breakoutDate, date(25));
  assert.equal(r.breakoutLow, 99);
  assert.equal(r.breakoutHigh, 108);
  assert.equal(r.midpoint, 103.5); // (108 + 99) / 2
  assert.equal(r.currentPrice, 103.5); // close of the latest candle
  assert.equal(r.distanceFromMidpoint, 0);
  assert.equal(r.volMultiple, 3); // 3000 / average(1000 x 20)
  assert.equal(r.prevHigh, 101); // highest high of the 20 candles before the breakout
  assert.equal(r.maxPriceAfter, 112); // highest high after the breakout (candle 26)
  close(r.returnFromCloseToSubHigh, ((112 - 107) / 107) * 100); // 4.6729%
  close(r.retracementHigh, ((112 - 103.5) / 112) * 100); // 7.5893%
  assert.equal(r.candles.length, 30);
});

test("the result has exactly the agreed fields (plus the instrument token for live prices)", () => {
  const r = scanStock(stock(standard()));
  assert.deepEqual(Object.keys(r).sort(), [
    "bIndex", "breakoutDate", "breakoutHigh", "breakoutLow", "candles", "companyName", "currentPrice", "daysSince",
    "distanceFromMidpoint", "instrumentToken", "maxPriceAfter", "midpoint", "prevHigh", "retracementHigh",
    "returnFromCloseToSubHigh", "symbol", "volMultiple",
  ]);
});

test("the parameters are exactly the agreed ones", () => {
  assert.deepEqual({ ...PARAMS }, { volumeLookback: 20, volumeMultiplier: 3, priceLookback: 20, maxBreakoutAge: 20, midpointTolerancePct: 1 });
  assert.equal(MIN_CANDLES, 25);
});

// ------------------------------------------------------------- normalization ---
test("dates become YYYY-MM-DD and keep their own calendar day", () => {
  assert.equal(normalizeDate("2026-11-25"), "2026-11-25");
  assert.equal(normalizeDate("2026-11-25T00:00:00+05:30"), "2026-11-25"); // not shifted to the 24th by a time zone
  assert.equal(normalizeDate("2026-11-25 09:15:00"), "2026-11-25");
  assert.equal(normalizeDate("not a date"), null);
  assert.equal(normalizeDate(null), null);
  assert.equal(normalizeDate(""), null);
  assert.equal(normalizeDate(new Date(2026, 10, 25, 12)), "2026-11-25");
});

test("prices and volume become numbers, candles are sorted oldest first, bad candles are dropped", () => {
  const out = normalizeCandles([
    { date: "2026-01-03T00:00:00+05:30", open: "3", high: "4", low: "2", close: "3.5", volume: "300" },
    { date: "2026-01-01", open: 1, high: 2, low: 0.5, close: 1.5, volume: 100 },
    { date: "2026-01-02", open: "x", high: 2, low: 1, close: 1, volume: 1 }, // not a number: dropped
    { date: "garbage", open: 1, high: 1, low: 1, close: 1, volume: 1 }, // no usable date: dropped
    null,
    { date: "2026-01-04", open: 1, high: 1, low: 1, close: 1 }, // no volume: dropped
  ]);
  assert.deepEqual(out, [
    { date: "2026-01-01", open: 1, high: 2, low: 0.5, close: 1.5, volume: 100 },
    { date: "2026-01-03", open: 3, high: 4, low: 2, close: 3.5, volume: 300 },
  ]);
  assert.ok(out.every((c) => ["open", "high", "low", "close", "volume"].every((k) => typeof c[k] === "number")));
});

test("Kite-style array candles and alternative key names are understood", () => {
  const out = normalizeCandles([["2026-01-01T00:00:00+05:30", 1, 2, 0.5, 1.5, 100], { timestamp: "2026-01-02", o: 2, h: 3, l: 1, c: 2.5, v: 200 }]);
  assert.deepEqual(out.map((c) => [c.date, c.close, c.volume]), [["2026-01-01", 1.5, 100], ["2026-01-02", 2.5, 200]]);
});

test("a stock is normalised from either naming style", () => {
  const a = normalizeStock({ symbol: "siemens", company_name: "Siemens Ltd.", instrument_token: 806401, nifty_flags: { nifty50: true }, candles: [] });
  const b = normalizeStock({ tradingsymbol: "SIEMENS", companyName: "Siemens Ltd.", instrumentToken: "806401", candles: [] });
  assert.deepEqual([a.symbol, a.companyName, a.instrumentToken, a.niftyFlags], ["SIEMENS", "Siemens Ltd.", 806401, { nifty50: true }]);
  assert.deepEqual([b.symbol, b.companyName, b.instrumentToken], ["SIEMENS", "Siemens Ltd.", 806401]);
});

test("unsorted input gives the same answer as sorted input", () => {
  const raw = standard().map((c) => ({ ...c }));
  const shuffled = [...raw].reverse();
  const a = scanStocks([{ symbol: "AAA", instrument_token: 1, candles: raw }]).results[0];
  const b = scanStocks([{ symbol: "AAA", instrument_token: 1, candles: shuffled }]).results[0];
  assert.equal(b.bIndex, a.bIndex);
  assert.equal(b.midpoint, a.midpoint);
});

// ------------------------------------------------------------ candle counts ---
test("fewer than 25 candles: not scanned for setups, but still counted as scanned", () => {
  const short = candles(24, { 21: BREAKOUT, 22: { high: 112, close: 110 }, 23: { open: 104, high: 105, low: 103, close: 103.5 } });
  const { results, scanned } = scanStocks([stock(short, "SHORT"), stock(standard(), "LONG")]);
  assert.equal(scanned, 2);
  assert.deepEqual(results.map((r) => r.symbol), ["LONG"]);
});

test("exactly 25 candles is enough", () => {
  // n = 25: indices 23..20 are eligible. Breakout at 21 (age 3).
  const c = candles(25, { 21: BREAKOUT, 22: { high: 112, close: 110 }, 23: { high: 106, close: 104 }, 24: { open: 104, high: 105, low: 103, close: 103.5 } });
  const r = scanStock(stock(c));
  assert.equal(r.bIndex, 21);
  assert.equal(r.daysSince, 3);
});

test("the earliest candidate needs 20 candles before it", () => {
  const withBreakoutAt = (i) => {
    const patches = { [i]: BREAKOUT, [i + 1]: { high: 112, close: 110 }, 29: { open: 104, high: 105, low: 103, close: 103.5 } };
    return scanStock(stock(candles(30, patches)));
  };
  assert.equal(withBreakoutAt(20)?.bIndex, 20); // 20 candles before it: allowed
  assert.equal(withBreakoutAt(19), null); // only 19 candles before it: not eligible
});

// ---------------------------------------------------------------------- age ---
test("a breakout 20 candles old is accepted, 21 is not", () => {
  const n = 50; // latest index 49
  const at = (i) => scanStock(stock(candles(n, { [i]: BREAKOUT, [i + 1]: { high: 112, close: 110 }, 49: { open: 104, high: 105, low: 103, close: 103.5 } })));
  assert.equal(at(29)?.daysSince, 20); // 49 - 29 = 20 candles after it
  assert.equal(at(28), null); // 21 candles after it: too old
});

test("the latest candle is never the breakout candle", () => {
  const c = candles(30, { 29: { ...BREAKOUT } }); // a perfect breakout on the last day: nothing after it
  assert.equal(scanStock(stock(c)), null);
});

// ------------------------------------------------------------ breakout rules ---
test("volume must be at least 3x the average: exactly 3x passes, just under fails", () => {
  assert.ok(scanStock(stock(standard({ 25: { ...BREAKOUT, volume: 3000 } }))));
  assert.equal(scanStock(stock(standard({ 25: { ...BREAKOUT, volume: 2999 } }))), null);
  assert.ok(scanStock(stock(standard({ 25: { ...BREAKOUT, volume: 9000 } }))));
});

test("the average volume and the previous high exclude the breakout candle itself", () => {
  // If the candidate's own volume were included the average would be (19 x 1000 + 3000) / 20 = 1100 and 3000 would fail.
  // If its own high (108) were included the previous high would be 108, and a close of 107 would fail.
  const r = scanStock(stock(standard()));
  assert.equal(r.volMultiple, 3);
  assert.equal(r.prevHigh, 101);
});

test("the average volume uses exactly the 20 candles before the breakout", () => {
  // candles 5..24 average 1000 here. A huge volume on candle 4 (21 candles back) must not matter.
  const r = scanStock(stock(standard({ 4: { volume: 1_000_000 } })));
  assert.equal(r.volMultiple, 3);
  // ...but one on candle 5 (20 candles back) must: average = (19 x 1000 + 21000) / 20 = 2000, so 3000 is only 1.5x.
  assert.equal(scanStock(stock(standard({ 5: { volume: 21_000 } }))), null);
});

test("the breakout candle must close above its open", () => {
  assert.equal(scanStock(stock(standard({ 25: { ...BREAKOUT, open: 107 } }))), null); // close == open
  assert.equal(scanStock(stock(standard({ 25: { ...BREAKOUT, open: 108, high: 109 } }))), null); // close < open
});

test("the close must be strictly above the previous 20-candle high (101)", () => {
  assert.equal(scanStock(stock(standard({ 25: { ...BREAKOUT, close: 101 } }))), null); // equal: rejected
  assert.ok(scanStock(stock(standard({ 25: { ...BREAKOUT, close: 101.01 } }))));
});

test("the previous high counts highs, not closes, over exactly 20 candles", () => {
  assert.equal(scanStock(stock(standard({ 10: { high: 110 } }))), null); // a higher high inside the window: close 107 is no longer a breakout
  assert.ok(scanStock(stock(standard({ 4: { high: 110 } })))); // outside the window (21 back): ignored
});

test("the move must continue: a later high strictly above the breakout high", () => {
  const flat = { 26: { high: 108, close: 107 }, 27: { high: 107 }, 28: { high: 106 } }; // never exceeds 108
  assert.equal(scanStock(stock(standard(flat))), null);
  assert.ok(scanStock(stock(standard({ 26: { high: 108.01, close: 110 } }))));
});

test("a higher high BEFORE the breakout does not count as continuation", () => {
  const c = standard({ 26: { high: 107, close: 106 }, 27: { high: 107 }, 28: { high: 106 } });
  assert.equal(scanStock(stock(c)), null);
});

// ------------------------------------------------------------------ the retest ---
// A second set of numbers where the midpoint is a round 200: breakout high 210, low 190.
const BASE200 = { open: 200, high: 201, low: 199, close: 200.5, volume: 1000 };
const setup200 = (lastClose) =>
  candles(30, { 25: { open: 200, high: 210, low: 190, close: 209, volume: 3000 }, 26: { high: 215, close: 212 }, 29: { open: 200, high: 203, low: 197, close: lastClose } }, BASE200);

test("the latest close must be within 1% of the midpoint, either side", () => {
  assert.ok(scanStock(stock(setup200(202)))); // +1.00% exactly
  assert.ok(scanStock(stock(setup200(198)))); // -1.00% exactly
  assert.equal(scanStock(stock(setup200(202.01))), null); // +1.005%
  assert.equal(scanStock(stock(setup200(197.99))), null); // -1.005%
  const r = scanStock(stock(setup200(198.5)));
  close(r.distanceFromMidpoint, -0.75); // (198.5 - 200) / 200 x 100
  assert.equal(r.midpoint, 200);
});

// ----------------------------------------------------------- most recent wins ---
test("one result per stock: the most recent accepted setup wins", () => {
  // A at 22 (high 108, low 99, midpoint 103.5) and B at 26. B's volume must beat 3x the average, which now includes A's 3000:
  // (19 x 1000 + 3000) / 20 = 1100 -> 3300 needed. B's close must beat the previous high, which now includes A's 108.
  const c = candles(32, {
    22: BREAKOUT, 23: { high: 112, close: 110 },
    26: { open: 105, high: 118, low: 100, close: 116, volume: 3300 }, 27: { high: 120, close: 118 },
    31: { open: 109.5, high: 110, low: 108, close: 109 }, // B's midpoint is (118 + 100) / 2 = 109
  });
  const r = scanStock(stock(c));
  assert.equal(r.bIndex, 26);
  assert.equal(r.midpoint, 109);
  assert.equal(r.daysSince, 5);
});

test("when the most recent candidate fails the retest, an older one that passes is used", () => {
  // Same two breakouts, but the price now sits at A's midpoint 103.5, far from B's midpoint 109.
  const c = candles(32, {
    22: BREAKOUT, 23: { high: 112, close: 110 },
    26: { open: 105, high: 118, low: 100, close: 116, volume: 3300 }, 27: { high: 120, close: 118 },
    31: { open: 104, high: 105, low: 103, close: 103.5 },
  });
  const r = scanStock(stock(c));
  assert.equal(r.bIndex, 22);
  assert.equal(r.midpoint, 103.5);
  assert.equal(r.daysSince, 9);
});

test("zero average volume is not a usable average", () => {
  const c = candles(30, { 25: { ...BREAKOUT, volume: 5000 }, ...AFTER }, { ...BASE, volume: 0 });
  assert.equal(scanStock(stock(c)), null);
});

// -------------------------------------------------------------------- ranking ---
test("results are sorted by age, then by distance from the midpoint", () => {
  // all three: breakout 108/99, midpoint 103.5. The latest close sets the distance.
  const make = (age, lastClose, symbol) => {
    const n = 30;
    const i = n - 1 - age;
    const c = candles(n, { [i]: BREAKOUT, [i + 1]: { high: 112, close: 110 }, [n - 1]: { open: lastClose, high: lastClose + 1, low: lastClose - 1, close: lastClose } });
    return stock(c, symbol);
  };
  const { results } = scanStocks([
    make(5, 104.0, "S1"), // age 5, +0.48%
    make(3, 104.4, "S2"), // age 3, +0.87%
    make(3, 103.6, "S3"), // age 3, +0.10%
  ]);
  assert.deepEqual(results.map((r) => [r.symbol, r.daysSince]), [["S3", 3], ["S2", 3], ["S1", 5]]);
  close(results[0].distanceFromMidpoint, ((103.6 - 103.5) / 103.5) * 100);
});

test("equal age and distance keep the order of the data (a stable sort)", () => {
  const { results } = scanStocks([stock(standard(), "ZZZ"), stock(standard(), "AAA")]);
  assert.deepEqual(results.map((r) => r.symbol), ["ZZZ", "AAA"]);
});

test("a negative distance ranks by its absolute value", () => {
  const make = (lastClose, symbol) => stock(candles(30, { 25: BREAKOUT, 26: { high: 112, close: 110 }, 29: { open: lastClose, high: lastClose + 0.5, low: lastClose - 0.5, close: lastClose } }), symbol);
  const { results } = scanStocks([make(102.6, "FAR"), make(103.4, "NEAR")]); // -0.87% and -0.10%
  assert.deepEqual(results.map((r) => r.symbol), ["NEAR", "FAR"]);
});

test("empty or missing input is fine", () => {
  assert.deepEqual(scanStocks([]), { results: [], scanned: 0 });
  assert.deepEqual(scanStocks(undefined), { results: [], scanned: 0 });
  assert.deepEqual(scanStocks([{ symbol: "X", instrument_token: 1 }]), { results: [], scanned: 1 });
});

test("a stock with junk candles does not crash the scan of the others", () => {
  const junk = { symbol: "JUNK", instrument_token: 2, candles: [null, { date: "x" }, ...standard().slice(0, 5)] };
  const { results, scanned } = scanStocks([junk, { symbol: "OK", instrument_token: 3, candles: standard() }]);
  assert.equal(scanned, 2);
  assert.deepEqual(results.map((r) => r.symbol), ["OK"]);
});
