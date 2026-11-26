import assert from "node:assert/strict";
import test from "node:test";
import { MESSAGES, buildCandidate, buildCandidates, deriveRows, mergePlacementResults, selectReady, summarizeLive, toMap } from "./gtt.js";

const signal = (symbol, breakoutLow = 3903.3) => ({ symbol, companyName: `${symbol} Ltd.`, instrumentToken: 1, breakoutLow });
const prices = (map) => (s) => map[s.symbol] ?? null;

// ----------------------------------------------------------------- candidates ---
test("the buy price is the breakout candle low, never the LTP, and the stoploss is 5% below it", () => {
  const c = buildCandidate(signal("SIEMENS"), 4043);
  assert.equal(c.symbol, "SIEMENS");
  assert.equal(c.quantity, 1);
  assert.equal(c.buy_price, 3903.3);
  assert.ok(Math.abs(c.stoploss - 3903.3 * 0.95) < 1e-9);
  assert.equal(c.last_price, 4043);
  assert.notEqual(c.buy_price, c.last_price);
});

test("no buy price: the candidate keeps its row but has no buy and no stoploss", () => {
  for (const bad of [null, undefined, 0, -1, NaN]) {
    const c = buildCandidate({ symbol: "X", breakoutLow: bad }, 100);
    assert.equal(c.buy_price, null);
    assert.equal(c.stoploss, null);
  }
});

test("a missing or invalid last price becomes null", () => {
  for (const bad of [null, undefined, 0, NaN, "12"]) assert.equal(buildCandidate(signal("X"), bad).last_price, null);
});

test("candidates are built for every current signal, in order, with no hardcoded symbols", () => {
  const cs = buildCandidates([signal("B"), signal("A")], prices({ A: 1, B: 2 }));
  assert.deepEqual(cs.map((c) => [c.symbol, c.last_price]), [["B", 2], ["A", 1]]);
  assert.deepEqual(buildCandidates([], prices({})), []);
});

// ---------------------------------------------------------------- selectReady ---
const cand = (symbol, over = {}) => ({ symbol, quantity: 1, buy_price: 100, stoploss: 95, last_price: 101, ...over });

test("only rows the backend called ready, with buy, stoploss and a price, are sent", () => {
  const state = {
    OK: { buy_status: "ready", account_state: "clear" },
    HELD: { buy_status: "blocked", account_state: "blocked" },
    ACTIVE: { buy_status: "already_active", account_state: "already_active" },
    WAIT: { buy_status: "waiting_for_ltp", account_state: "waiting" },
    NOBUY: { buy_status: "ready", account_state: "clear" },
    NOLTP: { buy_status: "ready", account_state: "clear" },
    NOSTATE_ROW: undefined,
  };
  const picked = selectReady(
    [cand("OK"), cand("HELD"), cand("ACTIVE"), cand("WAIT"), cand("NOBUY", { buy_price: null, stoploss: null }), cand("NOLTP", { last_price: null }), cand("NOSTATE")],
    state
  );
  assert.deepEqual(picked.map((c) => c.symbol), ["OK"]);
});

test("rows with the old skip states are left out even if marked ready", () => {
  const state = {
    A: { buy_status: "ready", account_state: "position_exists" },
    B: { buy_status: "ready", account_state: "day_buy_order_exists" },
    C: { buy_status: "position_exists", account_state: "clear" },
  };
  assert.deepEqual(selectReady([cand("A"), cand("B"), cand("C")], state), []);
});

// ------------------------------------------------------------------ deriveRows ---
test("rows come only from the current signals, ranked from 1 in the signals' own order", () => {
  const rows = deriveRows([signal("B"), signal("A")], prices({ A: 10, B: 20 }), {}, false);
  assert.deepEqual(rows.map((r) => [r.rank, r.symbol]), [[1, "B"], [2, "A"]]);
  // a stock that leaves Algo Signals leaves the table, even if the backend once answered for it
  const after = deriveRows([signal("A")], prices({ A: 10 }), { A: { buy_status: "ready" }, B: { buy_status: "success" } }, false);
  assert.deepEqual(after.map((r) => r.symbol), ["A"]);
});

test("without a backend answer: waiting, checking, unavailable and plain not-placed rows", () => {
  const rows = deriveRows([signal("NOPRICE"), signal("NOBUY", null), signal("PLAIN")], prices({ NOBUY: 5, PLAIN: 5 }), {}, false);
  const by = Object.fromEntries(rows.map((r) => [r.symbol, r]));
  assert.deepEqual([by.NOPRICE.buyStatus, by.NOPRICE.message], ["waiting_for_ltp", MESSAGES.waiting]);
  assert.deepEqual([by.NOBUY.buyStatus, by.NOBUY.stoplossStatus, by.NOBUY.message], ["not_available", "not_available", MESSAGES.noBuyPrice]);
  assert.equal(by.NOBUY.buy, null);
  assert.equal(by.PLAIN.buyStatus, "not_placed");
  const checking = deriveRows([signal("PLAIN")], prices({ PLAIN: 5 }), {}, true);
  assert.deepEqual([checking[0].buyStatus, checking[0].stoplossStatus], ["checking", "checking"]);
});

test("a backend answer supplies the statuses, triggers and message", () => {
  const result = {
    symbol: "S", buy_price: 3903.3, stoploss: 3708.1, account_state: "clear", buy_status: "success", buy_trigger_id: "DUMMY-S-000001",
    stoploss_status: "planned_after_buy", stoploss_trigger_id: null, position_quantity: 0, day_buy_order_id: null, day_buy_order_status: null,
    message: "Dummy buy GTT created. No order sent to Kite. Stoploss planned after buy execution.", last_price: 1,
  };
  const [row] = deriveRows([signal("S")], prices({ S: 4050 }), { S: result }, false);
  assert.deepEqual([row.buy, row.stoploss, row.buyStatus, row.buyTrigger, row.stoplossStatus, row.positionQty], [3903.3, 3708.1, "success", "DUMMY-S-000001", "planned_after_buy", 0]);
  assert.equal(row.message, result.message);
  assert.equal(row.lastPrice, 4050); // the live price, not the backend's snapshot of 1
});

test("an existing buy GTT, day order and stoploss GTT are shown", () => {
  const result = {
    symbol: "S", buy_price: 1, stoploss: 1, account_state: "blocked", buy_status: "blocked", active_buy_trigger_id: "777", buy_trigger_id: null,
    day_buy_order_id: "2611001", day_buy_order_status: "COMPLETE", position_quantity: 3, stoploss_status: "already_active", active_stoploss_trigger_id: "55", stoploss_trigger_id: "55", message: "x",
  };
  const [row] = deriveRows([signal("S")], prices({ S: 5 }), { S: result }, false);
  assert.deepEqual([row.buyTrigger, row.dayOrder, row.stoplossTrigger, row.positionQty], ["777", { id: "2611001", status: "COMPLETE" }, "55", 3]);
});

test("last price is null (shown as Waiting) when there is no live or snapshot price", () => {
  assert.equal(deriveRows([signal("S")], prices({}), {}, false)[0].lastPrice, null);
});

test("placement answers replace state answers", () => {
  const merged = mergePlacementResults([{ symbol: "A", buy_status: "ready" }, { symbol: "B", buy_status: "blocked" }], [{ symbol: "A", buy_status: "success" }]);
  assert.deepEqual([merged.A.buy_status, merged.B.buy_status], ["success", "blocked"]);
  assert.deepEqual(toMap([{ symbol: "A" }]), { A: { symbol: "A" } });
  assert.deepEqual(mergePlacementResults([], undefined), {});
});

test("the confirmation totals are exact to the paisa", () => {
  assert.deepEqual(summarizeLive([{ buy_price: 3903.3, quantity: 1 }, { buy_price: 99, quantity: 1 }, { buy_price: 0.1, quantity: 1 }, { buy_price: 0.2, quantity: 1 }]), { count: 4, total: 4002.6 });
  assert.deepEqual(summarizeLive([]), { count: 0, total: 0 });
});
