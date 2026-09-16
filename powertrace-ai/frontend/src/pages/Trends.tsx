import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { Download, LineChart as LineChartIcon } from 'lucide-react'
import { getToken } from '@/lib/api'
import { apiUrl } from '@/lib/config'
import { useApi, usePolling, useSelectedProject } from '@/lib/hooks'
import type { Controller } from '@/lib/types'
import { Empty, Panel, Spinner } from '@/components/ui'

const WINDOWS = [
  { label: '1 s', seconds: 1 }, { label: '10 s', seconds: 10 },
  { label: '1 min', seconds: 60 }, { label: '10 min', seconds: 600 },
  { label: '1 h', seconds: 3600 },
]

const PARAMETERS = [
  'voltage_L1_L2', 'voltage_L2_L3', 'voltage_L3_L1', 'current_L1', 'current_L2',
  'current_L3', 'frequency', 'kw', 'kvar', 'kva', 'power_factor', 'rpm',
  'oil_pressure', 'coolant_temperature', 'battery_voltage', 'control_voltage',
]

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#ef4444', '#06b6d4']

interface Series {
  key: string
  points: Array<{ t: number; v: number }>
  statistics: { count: number; min?: number; max?: number; avg?: number; last?: number }
}

export function Trends() {
  const [projectId] = useSelectedProject()
  const { data: controllers } = useApi<Controller[]>(
    projectId ? `/api/controllers?project_id=${projectId}` : null)
  const [controllerId, setControllerId] = useState<number | null>(null)
  const [selected, setSelected] = useState<string[]>(['voltage_L1_L2', 'frequency'])
  const [seconds, setSeconds] = useState(600)

  useEffect(() => {
    if (controllerId === null && controllers?.length) setControllerId(controllers[0].id)
  }, [controllers, controllerId])

  const path = controllerId
    ? `/api/trends?controller_id=${controllerId}&keys=${selected.join(',')}&seconds=${seconds}`
    : null
  const { data } = usePolling<{ series: Series[]; note: string }>(path, 2000)

  if (!projectId) return <Empty icon={LineChartIcon} title="Select a project" />
  if (!controllers) return <Spinner />

  // Recharts needs one row per timestamp; series are sampled independently so
  // they're merged on a rounded second rather than assumed aligned.
  const merged: Array<Record<string, number | string>> = []
  if (data?.series.length) {
    const byTime = new Map<number, Record<string, number | string>>()
    for (const series of data.series) {
      for (const point of series.points) {
        const bucket = Math.round(point.t)
        const row = byTime.get(bucket) ?? {
          t: bucket,
          label: new Date(bucket * 1000).toLocaleTimeString([], { hour12: false }),
        }
        row[series.key] = point.v
        byTime.set(bucket, row)
      }
    }
    merged.push(...[...byTime.values()].sort((a, b) => (a.t as number) - (b.t as number)))
  }

  const exportUrl = controllerId
    ? `/api/trends/export?controller_id=${controllerId}&keys=${selected.join(',')}&seconds=${seconds}`
    : '#'

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 flex-wrap">
        <select className="input w-auto" value={controllerId ?? ''}
          onChange={(e) => setControllerId(Number(e.target.value))}>
          {controllers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <div className="flex rounded border border-edge overflow-hidden">
          {WINDOWS.map((w) => (
            <button
              key={w.seconds}
              className={`px-2.5 py-1.5 text-xs ${seconds === w.seconds
                ? 'bg-blue-600 text-white' : 'bg-panel-700 text-slate-400 hover:bg-panel-600'}`}
              onClick={() => setSeconds(w.seconds)}
            >
              {w.label}
            </button>
          ))}
        </div>

        <button
          className="btn ml-auto"
          onClick={async () => {
            const token = getToken()
            const response = await fetch(apiUrl(exportUrl), {
              headers: token ? { Authorization: `Bearer ${token}` } : {},
            })
            const blob = await response.blob()
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `trend-${controllerId}.csv`
            link.click()
            URL.revokeObjectURL(url)
          }}
        >
          <Download className="h-3.5 w-3.5" /> Export CSV
        </button>
      </div>

      <Panel title="Parameters">
        <div className="flex flex-wrap gap-1.5">
          {PARAMETERS.map((key) => {
            const active = selected.includes(key)
            return (
              <button
                key={key}
                className={`px-2 py-1 rounded border text-2xs font-medium ${active
                  ? 'border-blue-500 bg-blue-600/20 text-blue-200'
                  : 'border-edge bg-panel-700 text-slate-400 hover:text-slate-200'}`}
                onClick={() => setSelected((prev) => active
                  ? prev.filter((k) => k !== key)
                  : prev.length < 6 ? [...prev, key] : prev)}
              >
                {key}
              </button>
            )
          })}
        </div>
        <p className="text-2xs text-slate-600 mt-2">
          Up to six series. Mixing units on one axis is allowed but read the statistics
          table rather than comparing curve heights.
        </p>
      </Panel>

      <Panel title="Trend">
        <div className="h-80">
          {merged.length === 0 ? (
            <Empty title="No samples in this window"
              hint="The trend buffer is in memory and fills as the controller is polled." />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
                <CartesianGrid stroke="#1c2431" strokeDasharray="3 3" />
                <XAxis dataKey="label" stroke="#475569" fontSize={10} minTickGap={40} />
                <YAxis stroke="#475569" fontSize={10} domain={['auto', 'auto']} />
                <Tooltip
                  contentStyle={{ background: '#10151e', border: '1px solid #27303f',
                    borderRadius: 4, fontSize: 11 }}
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {selected.map((key, i) => (
                  <Line key={key} type="monotone" dataKey={key} dot={false}
                    stroke={COLORS[i % COLORS.length]} strokeWidth={1.5}
                    isAnimationActive={false} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {data?.series.length ? (
        <Panel title="Statistics" dense>
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Parameter</th>
                <th className="th text-right">Samples</th>
                <th className="th text-right">Min</th>
                <th className="th text-right">Max</th>
                <th className="th text-right">Average</th>
                <th className="th text-right">Last</th>
              </tr>
            </thead>
            <tbody>
              {data.series.map((s) => (
                <tr key={s.key} className="table-row">
                  <td className="td font-mono text-xs">{s.key}</td>
                  <td className="td text-right text-xs">{s.statistics.count}</td>
                  <td className="td text-right value text-xs">
                    {s.statistics.min?.toFixed(2) ?? '—'}
                  </td>
                  <td className="td text-right value text-xs">
                    {s.statistics.max?.toFixed(2) ?? '—'}
                  </td>
                  <td className="td text-right value text-xs">
                    {s.statistics.avg?.toFixed(2) ?? '—'}
                  </td>
                  <td className="td text-right value text-xs text-slate-100">
                    {s.statistics.last?.toFixed(2) ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-2xs text-slate-600 px-3 py-2">{data.note}</p>
        </Panel>
      ) : null}
    </div>
  )
}
