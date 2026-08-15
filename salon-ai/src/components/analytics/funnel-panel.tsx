export function FunnelPanel({ stages }: { stages: { stage: string; value: number }[] }) {
  const max = Math.max(...stages.map((s) => s.value), 1);
  return (
    <div className="glass-panel p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">Conversion Funnel</p>
      <div className="space-y-3">
        {stages.map((s, i) => {
          const pct = Math.round((s.value / max) * 100);
          const prevValue = i > 0 ? stages[i - 1].value : s.value;
          const dropOff = prevValue > 0 ? Math.round((s.value / prevValue) * 100) : 100;
          return (
            <div key={s.stage}>
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="text-muted">{s.stage}</span>
                <span className="font-medium">
                  {s.value.toLocaleString()} {i > 0 && <span className="text-muted-2">({dropOff}%)</span>}
                </span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-accent to-accent-2"
                  style={{ width: `${Math.max(pct, 3)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
