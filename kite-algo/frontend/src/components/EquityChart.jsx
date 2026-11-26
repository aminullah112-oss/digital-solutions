import { useEffect, useMemo, useRef, useState } from "react";
import { formatCompact, formatDate, formatMoney } from "../utils/format.js";

// Line chart drawn as plain SVG, so no chart library is needed.
// To change a line's color, edit the --chart-* variables in styles/theme.css.
const SERIES = [
  { key: "strategy", label: "Strategy", color: "var(--chart-strategy)", dash: undefined },
  { key: "nifty100", label: "Nifty 100 index", color: "var(--chart-index)", dash: undefined },
  { key: "same_stocks", label: "Same stocks, buy and hold", color: "var(--chart-same)", dash: "6 4" },
];

const HEIGHT = 320;
const M = { top: 12, right: 16, bottom: 30, left: 64 };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Round tick values (1, 2, 2.5, 5 x 10^n) between min and max.
function niceTicks(min, max, count = 5) {
  const span = max - min || 1;
  const raw = span / count;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) ticks.push(v);
  return ticks;
}

// Tick positions on regular calendar boundaries: every 1, 2, 3, 6, 12 or 24 months,
// whichever is the finest that still fits `maxLabels` labels.
function monthTicks(curve, maxLabels) {
  const starts = [];
  curve.forEach((p, i) => {
    if (i > 0 && p.date.slice(0, 7) !== curve[i - 1].date.slice(0, 7)) starts.push(i);
  });
  const monthNumber = (i) => Number(curve[i].date.slice(0, 4)) * 12 + Number(curve[i].date.slice(5, 7)) - 1;
  for (const step of [1, 2, 3, 6, 12, 24]) {
    const picked = starts.filter((i) => monthNumber(i) % step === 0);
    if (picked.length <= maxLabels) return picked;
  }
  return [];
}

export default function EquityChart({ curve }) {
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const update = () => setWidth(Math.max(240, Math.floor(el.clientWidth)));
    update();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const n = curve.length;
  const plotW = width - M.left - M.right;
  const plotH = HEIGHT - M.top - M.bottom;

  const model = useMemo(() => {
    const lines = SERIES.filter((s) => curve.some((p) => p[s.key] !== null));
    const values = lines.flatMap((s) => curve.map((p) => p[s.key]).filter((v) => v !== null));
    const lo = Math.min(...values);
    const hi = Math.max(...values);
    const pad = (hi - lo) * 0.06 || hi * 0.05 || 1;
    const yMin = lo - pad;
    const yMax = hi + pad;
    const x = (i) => M.left + (n > 1 ? (i / (n - 1)) * plotW : 0);
    const y = (v) => M.top + (1 - (v - yMin) / (yMax - yMin)) * plotH;
    const paths = lines.map((s) => {
      let d = "";
      curve.forEach((p, i) => {
        if (p[s.key] === null) return;
        d += `${d ? "L" : "M"}${x(i).toFixed(1)} ${y(p[s.key]).toFixed(1)}`;
      });
      return { ...s, d, last: [...curve].reverse().find((p) => p[s.key] !== null)[s.key] };
    });
    return { paths, x, y, yTicks: niceTicks(yMin, yMax), xTicks: monthTicks(curve, Math.min(7, Math.floor(plotW / 70))) };
  }, [curve, n, plotW, plotH]);

  function handleMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - rect.left) / plotW) * (n - 1));
    setHover(Math.min(n - 1, Math.max(0, i)));
  }

  const point = hover === null ? null : curve[hover];
  const hoverX = hover === null ? 0 : model.x(hover);
  const summary = model.paths.map((p) => `${p.label} ended at ${formatMoney(p.last)}`).join(". ");

  return (
    <div>
      <ul className="chart-legend">
        {model.paths.map((p) => (
          <li className="legend-item" key={p.key}>
            <svg width="26" height="10" aria-hidden="true">
              <line x1="0" y1="5" x2="26" y2="5" stroke={p.color} strokeWidth="2.5" strokeDasharray={p.dash} />
            </svg>
            <span>{p.label}</span>
            <strong>{formatMoney(p.last)}</strong>
          </li>
        ))}
      </ul>

      <div className="chart-wrap" ref={wrapRef}>
        <svg width={width} height={HEIGHT} role="img" aria-label={`Equity curve. ${summary}.`}>
          <g aria-hidden="true">
            {model.yTicks.map((v) => (
              <g key={v}>
                <line x1={M.left} x2={width - M.right} y1={model.y(v)} y2={model.y(v)} stroke="var(--border)" strokeWidth="1" />
                <text x={M.left - 8} y={model.y(v) + 4} textAnchor="end" fontSize="11.5" fill="var(--text-muted)">
                  {formatCompact(v)}
                </text>
              </g>
            ))}
            {model.xTicks.map((i) => (
              <text key={i} x={model.x(i)} y={HEIGHT - 8} textAnchor="middle" fontSize="11.5" fill="var(--text-muted)">
                {`${MONTHS[Number(curve[i].date.slice(5, 7)) - 1]} ${curve[i].date.slice(0, 4)}`}
              </text>
            ))}
            {model.paths.map((p) => (
              <path key={p.key} d={p.d} fill="none" stroke={p.color} strokeWidth="2" strokeDasharray={p.dash} strokeLinejoin="round" />
            ))}
            {point && (
              <g>
                <line x1={hoverX} x2={hoverX} y1={M.top} y2={M.top + plotH} stroke="var(--text-muted)" strokeWidth="1" strokeDasharray="3 3" />
                {model.paths.map(
                  (p) =>
                    point[p.key] !== null && (
                      <circle key={p.key} cx={hoverX} cy={model.y(point[p.key])} r="4" fill="var(--surface)" stroke={p.color} strokeWidth="2" />
                    )
                )}
              </g>
            )}
          </g>
          <rect
            x={M.left}
            y={M.top}
            width={plotW}
            height={plotH}
            fill="transparent"
            onMouseMove={handleMove}
            onMouseLeave={() => setHover(null)}
          />
        </svg>

        {point && (
          <div className="chart-tooltip" style={{ left: hoverX, top: M.top, transform: hoverX > width / 2 ? "translateX(calc(-100% - 12px))" : "translateX(12px)" }}>
            <div className="tooltip-date">{formatDate(point.date)}</div>
            {model.paths.map(
              (p) =>
                point[p.key] !== null && (
                  <div className="tooltip-row" key={p.key}>
                    <span className="tooltip-dot" style={{ background: p.color }} aria-hidden="true" />
                    <span>{p.label}</span>
                    <strong>{formatMoney(point[p.key])}</strong>
                  </div>
                )
            )}
          </div>
        )}
      </div>
    </div>
  );
}
