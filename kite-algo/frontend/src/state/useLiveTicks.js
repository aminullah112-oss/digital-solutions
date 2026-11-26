import { useEffect, useMemo, useState } from "react";

// One websocket for the instrument tokens you pass in (here: the stocks Algo Signals currently shows).
// The backend relays Kite's live ticks. The browser never sees the access token.
// Returns { prices: { token: last_price }, status }.

const FLUSH_MS = 250; // batch ticks so React re-renders a few times a second, not on every tick
const RETRY_MS = [1000, 2000, 5000, 10000, 15000];

export function useLiveTicks(tokens) {
  const key = useMemo(
    () => [...new Set(tokens)].filter((t) => Number.isFinite(t)).sort((a, b) => a - b).join(","),
    [tokens]
  );
  const [prices, setPrices] = useState({});
  const [status, setStatus] = useState({ state: "idle", message: "" });

  useEffect(() => {
    if (!key) {
      setStatus({ state: "idle", message: "" });
      return undefined;
    }
    let closed = false;
    let socket = null;
    let retryTimer = null;
    let flushTimer = null;
    let attempt = 0;
    let pending = {};

    const flush = () => {
      flushTimer = null;
      const batch = pending;
      pending = {};
      setPrices((prev) => ({ ...prev, ...batch }));
    };

    const open = () => {
      setStatus({ state: "connecting", message: "" });
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws/ticks?tokens=${key}&mode=full`);
      socket.onopen = () => {
        attempt = 0;
      };
      socket.onmessage = (event) => {
        let msg;
        try {
          msg = JSON.parse(event.data);
        } catch {
          return;
        }
        if (msg.type === "status") {
          setStatus({ state: msg.connected ? "subscribed" : "waiting", message: "" });
        } else if (msg.type === "error") {
          setStatus({ state: "error", message: msg.message || "" });
        } else if (msg.type === "ticks") {
          for (const t of msg.ticks || []) {
            if (typeof t.last_price === "number") pending[t.instrument_token] = t.last_price;
          }
          if (flushTimer === null) flushTimer = setTimeout(flush, FLUSH_MS);
        }
      };
      socket.onclose = (event) => {
        if (closed) return;
        if (event.code === 4401) {
          setStatus({ state: "login", message: "" });
          return; // not logged in: retrying won't help
        }
        if (event.code === 1008) {
          setStatus((s) => (s.state === "error" ? s : { state: "error", message: "The live price request was refused." }));
          return;
        }
        setStatus({ state: "retrying", message: "" });
        retryTimer = setTimeout(open, RETRY_MS[Math.min(attempt++, RETRY_MS.length - 1)]);
      };
    };

    open();
    return () => {
      closed = true;
      clearTimeout(retryTimer);
      clearTimeout(flushTimer);
      if (socket) socket.close();
    };
  }, [key]);

  return { prices, status };
}

export function liveStatusText(status, count) {
  const symbols = `${count} ${count === 1 ? "symbol" : "symbols"}`;
  switch (status.state) {
    case "idle":
      return "Live ticks: no symbols to subscribe";
    case "connecting":
      return `Live ticks: connecting for ${symbols}…`;
    case "waiting":
      return `Live ticks: waiting for Kite (${symbols})`;
    case "subscribed":
      return `Live ticks: subscribed to ${symbols}`;
    case "retrying":
      return "Live ticks: disconnected, retrying…";
    case "login":
      return "Live ticks: login required";
    case "error":
      return `Live ticks: ${status.message || "unavailable"}`;
    default:
      return "Live ticks";
  }
}
