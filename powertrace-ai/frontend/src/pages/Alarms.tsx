import { useState } from 'react'
import { AlertTriangle, Check, Clock } from 'lucide-react'
import { api } from '@/lib/api'
import { usePolling, useSelectedProject } from '@/lib/hooks'
import type { Alarm } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import { Empty, Panel, SafetyNotice, SourceBadge, Spinner, StatusDot } from '@/components/ui'

interface EventRow {
  timestamp: string; category: string; code: string; message: string
  severity: string; source: string; quality: string
  value: number | null; unit: string
}

export function Alarms() {
  const [projectId] = useSelectedProject()
  const [minutes, setMinutes] = useState(60)
  const { data: alarms, reload } = usePolling<Alarm[]>(
    projectId ? `/api/alarms?project_id=${projectId}&limit=200` : null, 3000)
  const { data: events } = usePolling<{ events: EventRow[] }>(
    projectId ? `/api/alarms/events?project_id=${projectId}&minutes=${minutes}` : null, 3000)

  if (!projectId) return <Empty icon={AlertTriangle} title="Select a project" />
  if (!alarms) return <Spinner />

  const active = alarms.filter((a) => a.is_active)
  const history = alarms.filter((a) => !a.is_active)

  const acknowledge = async (id: number) => {
    await api.post(`/api/alarms/${id}/acknowledge`)
    void reload()
  }

  return (
    <div className="space-y-4">
      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title={`Active alarms (${active.length})`} dense>
          {active.length === 0 ? (
            <Empty icon={Check} title="No active alarms" />
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Severity</th>
                  <th className="th">Code</th>
                  <th className="th">Description</th>
                  <th className="th">Raised</th>
                  <th className="th w-px" />
                </tr>
              </thead>
              <tbody>
                {active.map((a) => (
                  <tr key={a.id} className="table-row">
                    <td className="td">
                      <StatusDot
                        tone={a.severity === 'SHUTDOWN' ? 'fault'
                          : a.severity === 'WARNING' ? 'warn' : 'fault'}
                        label={a.severity}
                      />
                    </td>
                    <td className="td font-mono text-xs text-slate-300">{a.code}</td>
                    <td className="td text-xs">
                      {a.description || (
                        <span className="italic text-slate-500">
                          No definition imported for this code
                        </span>
                      )}
                      <div className="mt-0.5">
                        <SourceBadge source={a.source as never} />
                        {a.description_source !== 'CATALOGUE' && a.description && (
                          <span className="ml-1 text-[9px] text-slate-600">
                            text from {a.description_source.toLowerCase()}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="td text-2xs text-slate-500">{formatDateTime(a.raised_at)}</td>
                    <td className="td">
                      {a.acknowledged ? (
                        <span className="text-2xs text-slate-500">ACK</span>
                      ) : (
                        <button className="btn py-0.5" onClick={() => void acknowledge(a.id)}>
                          Ack
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel
          title="Event timeline"
          dense
          actions={
            <select className="input py-0.5 w-auto text-xs" value={minutes}
              onChange={(e) => setMinutes(Number(e.target.value))}>
              {[15, 60, 240, 1440].map((m) => (
                <option key={m} value={m}>last {m < 60 ? `${m} min` : `${m / 60} h`}</option>
              ))}
            </select>
          }
        >
          {!events?.events.length ? (
            <Empty icon={Clock} title="No events in this window" />
          ) : (
            <div className="max-h-[28rem] overflow-y-auto divide-y divide-edge/60">
              {/* Correlation is the point of this list: controller output
                  transitions, alarms and measurements on one time axis. */}
              {events.events.slice().reverse().map((e, i) => (
                <div key={i} className="px-4 py-2 flex items-start gap-3">
                  <span className="text-2xs font-mono text-slate-500 shrink-0 w-16">
                    {new Date(e.timestamp).toLocaleTimeString([], { hour12: false })}
                  </span>
                  <span className="text-[9px] font-bold uppercase w-24 shrink-0 text-slate-600">
                    {e.category}
                  </span>
                  <span className="text-xs text-slate-300 flex-1">{e.message}</span>
                  <SourceBadge source={e.source as never} quality={e.quality as never} />
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {history.length > 0 && (
        <Panel title={`Alarm history (${history.length})`} dense>
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Severity</th>
                <th className="th">Code</th>
                <th className="th">Description</th>
                <th className="th">Raised</th>
                <th className="th">Cleared</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(0, 50).map((a) => (
                <tr key={a.id} className="table-row">
                  <td className="td text-2xs text-slate-500">{a.severity}</td>
                  <td className="td font-mono text-xs text-slate-400">{a.code}</td>
                  <td className="td text-xs text-slate-400">{a.description || '—'}</td>
                  <td className="td text-2xs text-slate-500">{formatDateTime(a.raised_at)}</td>
                  <td className="td text-2xs text-slate-500">{formatDateTime(a.cleared_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <SafetyNotice tone="info">
        No alarm descriptions ship with this application. A code with no imported catalogue
        entry is shown as the raw code — import your controller's alarm list under Settings
        to resolve them.
      </SafetyNotice>
    </div>
  )
}
