"use client";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function BarPanel({
  title,
  data,
  dataKey,
  labelKey,
  color = "var(--accent)",
  valueFormatter,
  layout = "vertical",
}: {
  title: string;
  data: Record<string, unknown>[];
  dataKey: string;
  labelKey: string;
  color?: string;
  valueFormatter?: (v: number) => string;
  layout?: "vertical" | "horizontal";
}) {
  return (
    <div className="glass-panel p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">{title}</p>
      {data.length === 0 ? (
        <p className="py-8 text-center text-xs text-muted">No data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(180, data.length * 34)}>
          <BarChart data={data} layout={layout === "vertical" ? "vertical" : "horizontal"} margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" horizontal={layout !== "vertical"} vertical={layout === "vertical"} />
            {layout === "vertical" ? (
              <>
                <XAxis type="number" tick={{ fill: "#8b96a8", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey={labelKey}
                  tick={{ fill: "#8b96a8", fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={110}
                />
              </>
            ) : (
              <>
                <XAxis dataKey={labelKey} tick={{ fill: "#8b96a8", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#8b96a8", fontSize: 11 }} axisLine={false} tickLine={false} />
              </>
            )}
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{ background: "#10151f", border: "1px solid rgba(148,163,184,0.15)", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#e7ecf5" }}
              formatter={(v) => (valueFormatter && typeof v === "number" ? valueFormatter(v) : v)}
            />
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 4, 4]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
