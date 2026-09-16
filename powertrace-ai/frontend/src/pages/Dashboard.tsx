import { Link } from 'react-router-dom'
import { AlertTriangle, Cpu, Radio } from 'lucide-react'
import { usePolling, useSelectedProject } from '@/lib/hooks'
import type { DashboardPayload } from '@/lib/types'
import { formatDateTime, formatValue } from '@/lib/format'
import { Empty, ErrorNote, Metric, Panel, SafetyNotice, SourceBadge, Spinner, StatusDot }
  from '@/components/ui'

export function Dashboard() {
  const [projectId] = useSelectedProject()
  const path = projectId ? `/api/dashboard?project_id=${projectId}` : '/api/dashboard'
  const { data, error, loading, reload } = usePolling<DashboardPayload>(path, 2000)

  if (loading && !data) return <Spinner label="Loading dashboard…" />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!data) return null

  const s = data.summary
  const noData = s.contributing_controllers === 0

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        <Metric label="Controllers online" value={s.controllers_online}
          sub={`${s.controllers_offline} offline`}
          tone={s.controllers_online === 0 ? 'fault' : 'ok'} />
        <Metric label="Active faults" value={s.active_faults}
          tone={s.active_faults > 0 ? 'fault' : 'default'}
          sub={`${s.warnings} warnings`} />
        <Metric label="Generators running" value={s.generators_running}
          sub={`${s.generators_stopped} stopped`} />
        <Metric
          label="Total load"
          value={noData ? '—' : formatValue(s.total_load_kw, undefined, 0)}
          unit={noData ? undefined : 'kW'}
          sub={noData ? 'no controller reporting' : `${s.contributing_controllers} contributing`}
        />
        <Metric
          label="System voltage"
          value={noData ? '—' : formatValue(s.system_voltage_v, undefined, 0)}
          unit={noData ? undefined : 'V'}
          sub={noData ? 'no controller reporting' : 'mean of reporting units'}
        />
        <Metric
          label="Frequency"
          value={noData ? '—' : formatValue(s.frequency_hz, undefined, 2)}
          unit={noData ? undefined : 'Hz'}
          sub={noData ? 'no controller reporting' : undefined}
        />
      </div>

      {/* An aggregate over a partial set is a trap: state the denominator. */}
      {!noData && (
        <p className="text-2xs text-slate-500 px-1">{s.aggregate_note}</p>
      )}

      <div className="grid lg:grid-cols-3 gap-4">
        <Panel
          title="Controllers"
          className="lg:col-span-2"
          actions={<Link to="/controllers" className="btn py-1">Manage</Link>}
          dense
        >
          {data.controllers.length === 0 ? (
            <Empty icon={Cpu} title="No controllers configured"
              hint="Add a controller under Controllers, or seed the demo project from Settings." />
          ) : (
            <div className="divide-y divide-edge/60">
              {data.controllers.map((c) => {
                const online = c.connection_state === 'ONLINE'
                const degraded = c.connection_state === 'DEGRADED'
                return (
                  <div key={c.id} className="px-4 py-3 flex items-center gap-4">
                    <div className="w-52 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-slate-100 truncate">
                          {c.name}
                        </span>
                        {c.is_simulated && (
                          <span className="px-1 py-0.5 rounded bg-orange-500/15
                            border border-orange-500/30 text-[9px] font-bold text-orange-300">
                            SIM
                          </span>
                        )}
                      </div>
                      <div className="text-2xs text-slate-500 truncate">
                        {c.manufacturer} {c.model} · {c.host ?? 'no host'}
                      </div>
                    </div>

                    <StatusDot
                      tone={online ? 'ok' : degraded ? 'warn' : 'fault'}
                      label={c.connection_state}
                      title={c.last_error ?? undefined}
                    />

                    <div className="flex-1 grid grid-cols-4 gap-3">
                      {(['voltage_L1_L2', 'frequency', 'kw', 'engine_status'] as const).map((key) => {
                        const env = c.values[key]
                        return (
                          <div key={key}>
                            <div className="label">{env?.display_name ?? key}</div>
                            <div className="text-sm value text-slate-200">
                              {env ? formatValue(env.value, env.unit) : '—'}
                            </div>
                            {env && <SourceBadge source={env.source} quality={env.quality}
                              age={env.age_s} />}
                          </div>
                        )
                      })}
                    </div>

                    <Link to={`/live?controller=${c.id}`} className="btn py-1">Live</Link>
                  </div>
                )
              })}
            </div>
          )}
        </Panel>

        <Panel title="Active alarms" dense
          actions={<Link to="/alarms" className="btn py-1">All</Link>}>
          {data.alarms.length === 0 ? (
            <Empty icon={AlertTriangle} title="No active alarms" />
          ) : (
            <div className="divide-y divide-edge/60 max-h-[26rem] overflow-y-auto">
              {data.alarms.map((a) => (
                <div key={a.id} className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <StatusDot
                      tone={a.severity === 'SHUTDOWN' ? 'fault'
                        : a.severity === 'WARNING' ? 'warn' : 'fault'}
                      label={a.severity}
                    />
                    <span className="text-xs font-mono text-slate-300">{a.code}</span>
                    <span className="ml-auto text-[10px] text-slate-500">
                      {formatDateTime(a.raised_at)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    {a.description || (
                      <span className="italic text-slate-500">
                        No definition imported for this code.
                      </span>
                    )}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {noData && data.controllers.length > 0 && (
        <SafetyNotice tone="info">
          No controller is currently reporting, so no live values are shown. Nothing on this
          screen is a stale value presented as current — a point with no data reads “—”.
        </SafetyNotice>
      )}

      <div className="flex items-center gap-2 text-2xs text-slate-600">
        <Radio className="h-3 w-3" />
        Dashboard refreshes every 2 s. Live Data uses a WebSocket for per-poll updates.
      </div>
    </div>
  )
}
