import { useState } from 'react'
import { Cpu, Plug, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useSelectedProject } from '@/lib/hooks'
import type { Controller } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import { Empty, ErrorNote, Panel, SafetyNotice, Spinner, StatusDot } from '@/components/ui'

const PROTOCOLS = [
  { value: 'MODBUS_TCP', label: 'Modbus TCP', implemented: true },
  { value: 'SIMULATOR', label: 'Simulator (demo)', implemented: true },
  { value: 'MODBUS_RTU', label: 'Modbus RTU', implemented: false },
  { value: 'CAN_J1939', label: 'CAN / J1939', implemented: false },
  { value: 'OPC_UA', label: 'OPC UA', implemented: false },
  { value: 'MQTT', label: 'MQTT', implemented: false },
]

export function Controllers() {
  const [projectId] = useSelectedProject()
  const path = projectId ? `/api/controllers?project_id=${projectId}` : '/api/controllers'
  const { data, error, loading, reload } = useApi<Controller[]>(path)
  const [adding, setAdding] = useState(false)
  const [tests, setTests] = useState<Record<number, { ok: boolean; detail: string }>>({})
  const [busy, setBusy] = useState<number | null>(null)

  const test = async (id: number) => {
    setBusy(id)
    try {
      const result = await api.post<{ ok: boolean; detail: string }>(
        `/api/controllers/${id}/test`)
      setTests((prev) => ({ ...prev, [id]: result }))
    } catch (e) {
      setTests((prev) => ({ ...prev, [id]: { ok: false, detail: String(e) } }))
    } finally {
      setBusy(null)
    }
  }

  const togglePolling = async (controller: Controller) => {
    await api.post(`/api/controllers/${controller.id}/polling?enabled=${!controller.enabled}`)
    void reload()
  }

  const remove = async (controller: Controller) => {
    if (!confirm(`Delete controller "${controller.name}"? This cannot be undone.`)) return
    await api.delete(`/api/controllers/${controller.id}`)
    void reload()
  }

  if (loading && !data) return <Spinner />

  return (
    <div className="space-y-4">
      {error && <ErrorNote error={error} onRetry={reload} />}

      <Panel
        title="Controllers"
        actions={
          <>
            <button className="btn" onClick={() => void reload()}>
              <RefreshCw className="h-3.5 w-3.5" /> Refresh
            </button>
            <button className="btn btn-primary" onClick={() => setAdding(true)}
              disabled={!projectId}>
              <Plus className="h-3.5 w-3.5" /> Add controller
            </button>
          </>
        }
        dense
      >
        {!data?.length ? (
          <Empty icon={Cpu} title="No controllers configured"
            hint={projectId ? 'Add a controller with its real network settings.'
              : 'Select a project first.'} />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Name</th>
                <th className="th">Make / model</th>
                <th className="th">Protocol</th>
                <th className="th">Address</th>
                <th className="th">Register map</th>
                <th className="th">State</th>
                <th className="th">Last OK</th>
                <th className="th w-px">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c) => {
                const result = tests[c.id]
                return (
                  <>
                    <tr key={c.id} className="table-row">
                      <td className="td">
                        <div className="font-semibold text-slate-100">{c.name}</div>
                        {c.is_simulated && (
                          <span className="text-[10px] font-bold text-orange-300">SIMULATED</span>
                        )}
                      </td>
                      <td className="td text-slate-400">
                        {c.manufacturer || '—'} {c.model}
                      </td>
                      <td className="td text-slate-400">{c.protocol?.protocol ?? '—'}</td>
                      <td className="td font-mono text-xs text-slate-400">
                        {c.protocol?.host
                          ? `${c.protocol.host}:${c.protocol.port} / unit ${c.protocol.unit_id}`
                          : '—'}
                      </td>
                      <td className="td">
                        {c.register_map_id === null ? (
                          <span className="text-2xs text-amber-300">NONE — reads nothing</span>
                        ) : c.register_map_verified ? (
                          <span className="text-2xs text-emerald-300">VERIFIED</span>
                        ) : (
                          <span className="text-2xs text-amber-300">UNVERIFIED</span>
                        )}
                      </td>
                      <td className="td">
                        <StatusDot
                          tone={c.connection_state === 'ONLINE' ? 'ok'
                            : c.connection_state === 'DEGRADED' ? 'warn'
                            : c.connection_state === 'DISABLED' ? 'unknown' : 'fault'}
                          label={c.connection_state}
                          title={c.last_error ?? undefined}
                        />
                      </td>
                      <td className="td text-2xs text-slate-500">
                        {formatDateTime(c.last_ok_at)}
                      </td>
                      <td className="td">
                        <div className="flex items-center gap-1.5">
                          <button className="btn py-1" disabled={busy === c.id}
                            onClick={() => void test(c.id)}>
                            <Plug className="h-3 w-3" /> Test
                          </button>
                          <button className="btn py-1" onClick={() => void togglePolling(c)}>
                            {c.enabled ? 'Stop polling' : 'Start polling'}
                          </button>
                          <button className="btn btn-danger py-1" onClick={() => void remove(c)}>
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {(result || c.last_error) && (
                      <tr key={`${c.id}-detail`}>
                        <td colSpan={8} className="px-3 pb-2">
                          {result && (
                            <div className={`text-2xs rounded border px-2.5 py-1.5 ${result.ok
                              ? 'border-emerald-700/40 bg-emerald-950/20 text-emerald-200'
                              : 'border-red-700/40 bg-red-950/20 text-red-200'}`}>
                              {result.detail}
                            </div>
                          )}
                          {c.last_error && !result && (
                            <div className="text-2xs rounded border border-red-700/40
                              bg-red-950/20 text-red-200 px-2.5 py-1.5">
                              Last error: {c.last_error}
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                )
              })}
            </tbody>
          </table>
        )}
      </Panel>

      <SafetyNotice tone="info">
        A successful connection test confirms the socket only. It does not validate the unit ID
        or the register map — a wrong map decodes into plausible but wrong engineering values.
        Verify a few known readings against the controller's own display before trusting a map.
      </SafetyNotice>

      {adding && projectId && (
        <AddControllerDialog
          projectId={projectId}
          onClose={() => setAdding(false)}
          onCreated={() => { setAdding(false); void reload() }}
        />
      )}
    </div>
  )
}

function AddControllerDialog({ projectId, onClose, onCreated }: {
  projectId: number; onClose: () => void; onCreated: () => void
}) {
  const [form, setForm] = useState({
    name: '', manufacturer: '', model: '', controller_type: '', description: '',
    protocol: 'MODBUS_TCP', host: '', port: 502, unit_id: 1, poll_interval_ms: 1000,
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const simulated = form.protocol === 'SIMULATOR'
  const protocolMeta = PROTOCOLS.find((p) => p.value === form.protocol)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/controllers', {
        project_id: projectId,
        name: form.name,
        manufacturer: form.manufacturer,
        model: form.model,
        controller_type: form.controller_type,
        description: form.description,
        is_simulated: simulated,
        protocol: {
          protocol: form.protocol,
          host: simulated ? null : form.host,
          port: simulated ? null : Number(form.port),
          unit_id: Number(form.unit_id),
          poll_interval_ms: Number(form.poll_interval_ms),
        },
      })
      onCreated()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
      onClick={onClose}>
      <form
        className="panel w-full max-w-lg"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <div className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider">Add controller</h2>
        </div>
        <div className="p-4 space-y-3">
          <Field label="Controller name" required>
            <input className="input" required value={form.name}
              placeholder="e.g. PPU34 GENSET 01"
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Manufacturer">
              <input className="input" value={form.manufacturer}
                onChange={(e) => setForm({ ...form, manufacturer: e.target.value })} />
            </Field>
            <Field label="Model">
              <input className="input" value={form.model}
                onChange={(e) => setForm({ ...form, model: e.target.value })} />
            </Field>
          </div>

          <Field label="Protocol">
            <select className="input" value={form.protocol}
              onChange={(e) => setForm({ ...form, protocol: e.target.value })}>
              {PROTOCOLS.map((p) => (
                <option key={p.value} value={p.value} disabled={!p.implemented}>
                  {p.label}{p.implemented ? '' : ' — not implemented'}
                </option>
              ))}
            </select>
          </Field>

          {!protocolMeta?.implemented && (
            <p className="text-2xs text-amber-300">
              This transport is defined in the protocol layer but not implemented. Selecting it
              creates the controller; polling will report the adapter as unavailable.
            </p>
          )}

          {!simulated && (
            <div className="grid grid-cols-3 gap-3">
              <Field label="IP address / host" required>
                <input className="input" required={!simulated} value={form.host}
                  placeholder="192.168.1.101"
                  onChange={(e) => setForm({ ...form, host: e.target.value })} />
              </Field>
              <Field label="Port">
                <input className="input" type="number" value={form.port}
                  onChange={(e) => setForm({ ...form, port: Number(e.target.value) })} />
              </Field>
              <Field label="Unit ID">
                <input className="input" type="number" value={form.unit_id}
                  onChange={(e) => setForm({ ...form, unit_id: Number(e.target.value) })} />
              </Field>
            </div>
          )}

          <Field label="Polling interval (ms)">
            <input className="input" type="number" min={100} value={form.poll_interval_ms}
              onChange={(e) => setForm({ ...form, poll_interval_ms: Number(e.target.value) })} />
          </Field>

          <SafetyNotice tone="info">
            Enter this panel's actual configuration. PowerTrace AI does not guess a controller's
            address, unit ID or register layout, and it ships no vendor register maps — import
            one from your controller's published register list under Settings.
          </SafetyNotice>

          {error && <ErrorNote error={error} />}
        </div>
        <div className="px-4 py-3 border-t border-edge flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Creating…' : 'Create controller'}
          </button>
        </div>
      </form>
    </div>
  )
}

function Field({ label, required, children }: {
  label: string; required?: boolean; children: React.ReactNode
}) {
  return (
    <div>
      <label className="label block mb-1">
        {label}{required && <span className="text-red-400 ml-0.5">*</span>}
      </label>
      {children}
    </div>
  )
}
