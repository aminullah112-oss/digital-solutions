import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Gauge, WifiOff } from 'lucide-react'
import { useApi, useLiveValues, useSelectedProject } from '@/lib/hooks'
import type { Controller, ValueEnvelope } from '@/lib/types'
import { formatAge, formatTime, formatValue, qualityClass } from '@/lib/format'
import { Empty, Panel, SafetyNotice, SourceBadge, Spinner, StatusDot } from '@/components/ui'

const GROUPS: Array<{ key: string; title: string }> = [
  { key: 'generator', title: 'Generator' },
  { key: 'engine', title: 'Engine' },
  { key: 'controller', title: 'Controller' },
  { key: 'io', title: 'Discrete I/O' },
  { key: 'other', title: 'Other parameters' },
]

const TREND_KEYS = ['voltage_L1_L2', 'frequency', 'kw', 'current_L1'] as const

export function LiveData() {
  const [projectId] = useSelectedProject()
  const [params, setParams] = useSearchParams()
  const path = projectId ? `/api/controllers?project_id=${projectId}` : '/api/controllers'
  const { data: controllers, loading } = useApi<Controller[]>(path)

  const requested = params.get('controller')
  const [selected, setSelected] = useState<number | null>(requested ? Number(requested) : null)

  useEffect(() => {
    if (selected === null && controllers?.length) setSelected(controllers[0].id)
  }, [controllers, selected])

  const { values, connected, lastMessageAt } = useLiveValues(selected)
  const controller = controllers?.find((c) => c.id === selected)

  // Local history so the trend strips fill immediately, rather than waiting on
  // the server's buffer after a restart.
  const [history, setHistory] = useState<Array<Record<string, number | string>>>([])
  useEffect(() => { setHistory([]) }, [selected])
  useEffect(() => {
    if (!Object.keys(values).length) return
    setHistory((prev) => {
      const point: Record<string, number | string> = { t: formatTime(new Date().toISOString()) }
      for (const key of TREND_KEYS) {
        const value = values[key]?.value
        if (typeof value === 'number') point[key] = value
      }
      return [...prev, point].slice(-120)
    })
  }, [values])

  const grouped = useMemo(() => {
    const map: Record<string, ValueEnvelope[]> = {}
    for (const env of Object.values(values)) {
      (map[env.group] ??= []).push(env)
    }
    for (const list of Object.values(map)) list.sort((a, b) => a.key.localeCompare(b.key))
    return map
  }, [values])

  if (loading) return <Spinner />
  if (!controllers?.length) {
    return <Empty icon={Gauge} title="No controllers"
      hint="Configure a controller to see live data." />
  }

  const stale = lastMessageAt !== null && Date.now() - lastMessageAt > 8000
  const offline = controller?.connection_state !== 'ONLINE'
    && controller?.connection_state !== 'DEGRADED'

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 flex-wrap">
        <select
          className="input w-auto"
          value={selected ?? ''}
          onChange={(e) => {
            const id = Number(e.target.value)
            setSelected(id)
            setParams({ controller: String(id) })
          }}
        >
          {controllers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <StatusDot
          tone={connected ? 'ok' : 'fault'}
          label={connected ? 'WebSocket live' : 'WebSocket down'}
        />
        {controller && (
          <StatusDot
            tone={controller.connection_state === 'ONLINE' ? 'ok'
              : controller.connection_state === 'DEGRADED' ? 'warn' : 'fault'}
            label={`Controller ${controller.connection_state}`}
          />
        )}
        {lastMessageAt && (
          <span className={`text-2xs ${stale ? 'text-amber-300' : 'text-slate-500'}`}>
            last update {formatAge((Date.now() - lastMessageAt) / 1000)}
          </span>
        )}
      </div>

      {offline && (
        <SafetyNotice>
          <span className="inline-flex items-center gap-1.5 font-semibold">
            <WifiOff className="h-3.5 w-3.5" /> CONTROLLER OFFLINE
          </span>
          {controller?.last_error && (
            <div className="mt-1 font-mono text-[11px] opacity-80">{controller.last_error}</div>
          )}
          <div className="mt-1">
            No live values are shown while communication is down. Any value from before the
            loss has been cleared rather than left on screen without an age.
          </div>
        </SafetyNotice>
      )}

      {Object.keys(values).length === 0 ? (
        <Empty icon={Gauge} title="No values"
          hint={controller?.register_map_id === null && !controller?.is_simulated
            ? 'This controller has no register map, so nothing is being read. Import a verified map.'
            : 'Waiting for the first poll…'} />
      ) : (
        <>
          <div className="grid xl:grid-cols-2 gap-4">
            {TREND_KEYS.map((key) => {
              const env = values[key]
              if (!env || typeof env.value !== 'number') return null
              return (
                <Panel key={key} title={`${env.display_name} — last ${history.length} samples`}>
                  <div className="flex items-baseline gap-3 mb-2">
                    <span className={`text-3xl value ${qualityClass(env.quality)}`}>
                      {formatValue(env.value)}
                    </span>
                    <span className="text-sm text-slate-500">{env.unit}</span>
                    <SourceBadge source={env.source} quality={env.quality} age={env.age_s} />
                  </div>
                  <div className="h-28">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                        <XAxis dataKey="t" hide />
                        {/* Wide enough for a 4-digit line voltage plus units;
                            a clipped axis label is worse than no axis. */}
                        <YAxis stroke="#475569" fontSize={10} width={58}
                          domain={['auto', 'auto']} tickLine={false} axisLine={false} />
                        <Tooltip
                          contentStyle={{ background: '#10151e', border: '1px solid #27303f',
                            borderRadius: 4, fontSize: 11 }}
                          labelStyle={{ color: '#94a3b8' }}
                        />
                        <Line type="monotone" dataKey={key} stroke="#3b82f6" strokeWidth={1.5}
                          dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              )
            })}
          </div>

          {GROUPS.map(({ key, title }) => {
            const list = grouped[key]
            if (!list?.length) return null
            return (
              <Panel key={key} title={title} dense>
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="th">Parameter</th>
                      <th className="th text-right">Value</th>
                      <th className="th">Unit</th>
                      <th className="th">Provenance</th>
                      <th className="th">Timestamp</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((env) => (
                      <tr key={env.key} className="table-row">
                        <td className="td">
                          <span className="text-slate-200">{env.display_name}</span>
                          <span className="ml-2 font-mono text-[10px] text-slate-600">
                            {env.key}
                          </span>
                        </td>
                        <td className={`td text-right value ${qualityClass(env.quality)}`}>
                          {formatValue(env.value)}
                        </td>
                        <td className="td text-slate-500 text-xs">{env.unit || '—'}</td>
                        <td className="td">
                          <SourceBadge source={env.source} quality={env.quality} />
                        </td>
                        <td className="td text-2xs text-slate-500">
                          {formatTime(env.timestamp)}
                          {env.age_s !== undefined && env.age_s > 2 &&
                            ` (${formatAge(env.age_s)})`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )
          })}
        </>
      )}

      <SafetyNotice tone="info">
        Everything on this screen is controller-reported. A controller reporting an output as
        ON is not a measurement of voltage at a terminal — use Circuit Explorer and the
        measurement workflow for that distinction.
      </SafetyNotice>
    </div>
  )
}
