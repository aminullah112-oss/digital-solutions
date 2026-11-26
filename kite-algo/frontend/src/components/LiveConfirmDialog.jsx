import { useEffect, useRef } from "react";
import { summarizeLive } from "../lib/gtt.js";
import { formatMoney, formatPrice } from "../utils/format.js";

// LIVE mode only. Shows exactly which real buy GTTs are about to be placed and waits for an explicit yes.
// Cancel has the focus when it opens, Escape cancels, and clicking outside the box does nothing.
export default function LiveConfirmDialog({ pending, placing, onConfirm, onCancel }) {
  const cancelRef = useRef(null);
  const dialogRef = useRef(null);
  const { count, total } = summarizeLive(pending.rows);
  const limits = pending.limits;

  useEffect(() => {
    cancelRef.current?.focus();
  }, []);

  // Listen on the document, not just the box: a click on the backdrop moves focus to <body>,
  // and Escape / Tab must keep working from there.
  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  });

  function handleKeyDown(e) {
    if (e.key === "Escape") {
      e.stopPropagation();
      if (!placing) onCancel();
      return;
    }
    if (e.key === "Tab") {
      // keep the keyboard inside the dialog
      const items = [...dialogRef.current.querySelectorAll("button:not([disabled])")];
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (!dialogRef.current.contains(document.activeElement)) {
        e.preventDefault();
        (e.shiftKey ? last : first).focus();
      } else if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) e.preventDefault(); }}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="live-title"
        aria-describedby="live-desc"
        ref={dialogRef}
      >
        <h3 id="live-title">
          Place {count} real GTT {count === 1 ? "order" : "orders"} on Zerodha?
        </h3>
        <p id="live-desc">
          These are <strong>real</strong> buy GTT orders. Each becomes a LIMIT buy of 1 share (CNC) when its price is reached, which can
          happen days from now. <strong>No stoploss is placed automatically.</strong>
        </p>

        <div className="table-wrap flat">
          <table className="table dense">
            <caption className="sr-only">Orders that will be placed</caption>
            <thead>
              <tr>
                <th scope="col">Symbol</th>
                <th scope="col" className="num">Qty</th>
                <th scope="col" className="num">Trigger = limit price</th>
                <th scope="col" className="num">Stoploss (not placed)</th>
                <th scope="col" className="num">Last price</th>
              </tr>
            </thead>
            <tbody>
              {pending.rows.map((r) => (
                <tr key={r.symbol}>
                  <td className="symbol">{r.symbol}</td>
                  <td className="num">{r.quantity}</td>
                  <td className="num">{formatPrice(r.buy_price)}</td>
                  <td className="num muted-cell">{formatPrice(r.stoploss)}</td>
                  <td className="num">{r.last_price === null ? "—" : formatPrice(r.last_price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="modal-total">
          Total value if all fill: <strong>{formatMoney(total)}</strong>
          {limits && (
            <span className="muted-inline">
              {" "}
              · limits: {limits.max_orders_per_run} per run, {formatMoney(limits.max_order_value)} per order, {limits.max_orders_per_day} per day
            </span>
          )}
        </p>

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" ref={cancelRef} onClick={onCancel} disabled={placing}>
            Cancel
          </button>
          <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={placing}>
            {placing ? "Placing..." : `Place ${count} real GTT ${count === 1 ? "order" : "orders"}`}
          </button>
        </div>
      </div>
    </div>
  );
}
