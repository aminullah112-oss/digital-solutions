import { useState } from 'react'
import { Activity, Plus, ShieldAlert } from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useSelectedProject } from '@/lib/hooks'
import type { CircuitNode } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import {
  Empty, ErrorNote, Panel, SafetyNotice, SourceBadge, Spinner,
} from '@/components/ui'

interface Device { id: number; name: string; manufacturer: string; model: string
  transport: string; host: string | null; connection_state: string
  is_simulated: boolean; channel_count: number }

interface Channel {
  id: number; device_id: number; channel_tag: string; description: string
  input_type: string; max_rated_input: number | null; max_rated_input_unit: string
  isolation_rating_v: number | null; isolated: boolean; signal_conditioning: string
  conditioning_ratio: number; unit: string; calibration_due_at: string | null
  circuit_node_id: number | null; nominal_circuit_voltage_v: number | null
  safety_checks: Array<{ level: string; code: string; message: string }>
}

interface MeasurementRow {
  id: number; value: number; unit: string; quality: string; source: string
  method: string; instrument: string; technician: string; notes: string
  timestamp: string; circuit_node_id: number | null
}

export function Measurements() {
  const [projectId] = useSelectedProject()
  const { data: devices, reload: reloadDevices } = useApi<Device[]>(
    projectId ? `/api/measurements/devices?project_id=${projectId}` : null)
  const { data: channels } = useApi<Channel[]>(
    devices?.length ? `/api/measurements/channels?device_id=${devices[0].id}` : null,
    [devices?.length])
  const { data: nodes } = useApi<{ nodes: CircuitNode[] }>(
    projectId ? `/api/circuits/${projectId}?include_status=false` : null)
  const { data: measurements, reload, error } = useApi<MeasurementRow[]>(
    projectId ? `/api/measurements?project_id=${projectId}&limit=100` : null)

  const [recording, setRecording] = useState(false)

  if (!projectId) return <Empty icon={Activity} title="Select a project" />
  if (!devices) return <Spinner />

  const nodeName = (id: number | null) =>
    nodes?.nodes.find((n) => n.id === id)?.label ?? (id ? `node ${id}` : '—')

  return (
    <div className="space-y-4">
      {error && <ErrorNote error={error} onRetry={reload} />}

      <SafetyNotice>
        <strong>Never connect an ordinary computer or DAQ input directly to medium voltage.</strong>
        {' '}A channel bound to a circuit above 60 V must declare the rated PT/VT, CT or isolating
        transducer the signal arrives through. The application refuses configurations that imply
        a direct connection — but that check is on the configuration, not on what is actually
        wired in the field.
      </SafetyNotice>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Measurement gateways" dense>
          {devices.length === 0 ? (
            <Empty icon={Activity} title="No gateway configured"
              hint="Measurements can also be entered manually against a circuit node." />
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Transport</th>
                  <th className="th">Address</th>
                  <th className="th">Channels</th>
                  <th className="th">State</th>
                </tr>
              </thead>
              <tbody>
                {devices.map((d) => (
                  <tr key={d.id} className="table-row">
                    <td className="td">
                      <span className="text-slate-100">{d.name}</span>
                      {d.is_simulated && (
                        <span className="ml-2 text-[10px] font-bold text-orange-300">SIM</span>
                      )}
                    </td>
                    <td className="td text-xs text-slate-400">{d.transport}</td>
                    <td className="td text-xs font-mono text-slate-500">{d.host ?? '—'}</td>
                    <td className="td text-xs">{d.channel_count}</td>
                    <td className="td text-xs">{d.connection_state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Channel safety" dense>
          {!channels?.length ? (
            <Empty title="No channels" />
          ) : (
            <div className="divide-y divide-edge/60 max-h-80 overflow-y-auto">
              {channels.map((c) => {
                const errors = c.safety_checks.filter((s) => s.level === 'ERROR')
                const warnings = c.safety_checks.filter((s) => s.level === 'WARNING')
                return (
                  <div key={c.id} className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-slate-200">{c.channel_tag}</span>
                      <span className="text-2xs text-slate-500 truncate">{c.description}</span>
                      {errors.length > 0 && (
                        <ShieldAlert className="h-3.5 w-3.5 text-red-400 ml-auto shrink-0" />
                      )}
                    </div>
                    <div className="mt-1 grid grid-cols-4 gap-2 text-2xs text-slate-500">
                      <span>{c.input_type}</span>
                      <span>max {c.max_rated_input ?? '—'} {c.max_rated_input_unit}</span>
                      <span>iso {c.isolation_rating_v ?? '—'} V</span>
                      <span>
                        {c.signal_conditioning}
                        {c.conditioning_ratio !== 1 && ` ${c.conditioning_ratio}:1`}
                      </span>
                    </div>
                    {[...errors, ...warnings].map((check, i) => (
                      <p key={i} className={`text-2xs mt-1 ${check.level === 'ERROR'
                        ? 'text-red-300' : 'text-amber-300/80'}`}>
                        {check.code}: {check.message}
                      </p>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Recorded measurements"
        actions={
          <button className="btn btn-primary" onClick={() => setRecording(true)}>
            <Plus className="h-3.5 w-3.5" /> Record measurement
          </button>
        }
        dense
      >
        {!measurements?.length ? (
          <Empty icon={Activity} title="No measurements recorded" />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Point</th>
                <th className="th text-right">Value</th>
                <th className="th">Provenance</th>
                <th className="th">Method</th>
                <th className="th">Instrument</th>
                <th className="th">Technician</th>
                <th className="th">Time</th>
              </tr>
            </thead>
            <tbody>
              {measurements.map((m) => (
                <tr key={m.id} className="table-row">
                  <td className="td text-slate-200">{nodeName(m.circuit_node_id)}</td>
                  <td className="td text-right value text-slate-100">
                    {m.value} {m.unit}
                  </td>
                  <td className="td">
                    <SourceBadge source={m.source as never} quality={m.quality as never} />
                  </td>
                  <td className="td text-xs text-slate-400">{m.method}</td>
                  <td className="td text-xs text-slate-500">{m.instrument || '—'}</td>
                  <td className="td text-xs text-slate-500">{m.technician || '—'}</td>
                  <td className="td text-2xs text-slate-500">{formatDateTime(m.timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      {recording && nodes && (
        <RecordDialog
          projectId={projectId}
          nodes={nodes.nodes}
          onClose={() => setRecording(false)}
          onRecorded={() => { setRecording(false); void reload(); void reloadDevices() }}
        />
      )}
    </div>
  )
}

function RecordDialog({ projectId, nodes, onClose, onRecorded }: {
  projectId: number; nodes: CircuitNode[]; onClose: () => void; onRecorded: () => void
}) {
  const [form, setForm] = useState({
    circuit_node_id: nodes[0]?.id ?? 0, value: '', unit: 'V', instrument: '', notes: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const node = nodes.find((n) => n.id === form.circuit_node_id)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/measurements', {
        project_id: projectId,
        circuit_node_id: form.circuit_node_id,
        value: Number(form.value),
        unit: form.unit,
        method: 'MANUAL',
        instrument: form.instrument,
        notes: form.notes,
      })
      onRecorded()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
      onClick={onClose}>
      <form className="panel w-full max-w-md" onClick={(e) => e.stopPropagation()}
        onSubmit={submit}>
        <div className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider">
            Record a manual measurement
          </h2>
        </div>
        <div className="p-4 space-y-3">
          <div>
            <label className="label block mb-1">Measurement point</label>
            <select className="input" value={form.circuit_node_id}
              onChange={(e) => setForm({ ...form, circuit_node_id: Number(e.target.value) })}>
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>{n.label} ({n.key})</option>
              ))}
            </select>
          </div>

          {node?.medium_voltage && (
            <SafetyNotice>
              {node.label} is on a {node.nominal_voltage_v} V circuit. {node.safety_notice}
            </SafetyNotice>
          )}

          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="label block mb-1">Measured value</label>
              <input className="input" type="number" step="any" required value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })} />
            </div>
            <div>
              <label className="label block mb-1">Unit</label>
              <select className="input" value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value })}>
                {['V', 'A', 'ohm', 'Hz', 'degC', 'psi'].map((u) => (
                  <option key={u} value={u}>{u}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="label block mb-1">Instrument</label>
            <input className="input" value={form.instrument}
              placeholder="Make, model and serial of the meter used"
              onChange={(e) => setForm({ ...form, instrument: e.target.value })} />
          </div>

          <div>
            <label className="label block mb-1">Notes</label>
            <input className="input" value={form.notes}
              placeholder="Reference point, conditions, anything unusual"
              onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>

          {error && <ErrorNote error={error} />}
        </div>
        <div className="px-4 py-3 border-t border-edge flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Recording…' : 'Record'}
          </button>
        </div>
      </form>
    </div>
  )
}
