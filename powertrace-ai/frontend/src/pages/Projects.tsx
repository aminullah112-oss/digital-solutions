import { useState } from 'react'
import { Copy, FolderKanban, Plus } from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useSelectedProject } from '@/lib/hooks'
import type { Project } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import { Empty, ErrorNote, Panel, SafetyNotice, Spinner } from '@/components/ui'

export function Projects() {
  const { data, error, loading, reload } = useApi<Project[]>('/api/projects')
  const [, setProjectId] = useSelectedProject()
  const [creating, setCreating] = useState(false)
  const [duplicating, setDuplicating] = useState<Project | null>(null)

  if (loading && !data) return <Spinner />

  return (
    <div className="space-y-4">
      {error && <ErrorNote error={error} onRetry={reload} />}

      <Panel
        title="Projects"
        actions={
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            <Plus className="h-3.5 w-3.5" /> New project
          </button>
        }
        dense
      >
        {!data?.length ? (
          <Empty icon={FolderKanban} title="No projects"
            hint="A project is one panel: its controllers, schematics, circuit model and history." />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Name</th>
                <th className="th">Site</th>
                <th className="th">Panel</th>
                <th className="th">Nominal</th>
                <th className="th">Created</th>
                <th className="th w-px" />
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className="table-row">
                  <td className="td">
                    <button className="text-slate-100 hover:text-blue-300 font-medium"
                      onClick={() => setProjectId(p.id)}>
                      {p.name}
                    </button>
                    {p.is_demo && (
                      <span className="ml-2 px-1 py-0.5 rounded bg-orange-500/15
                        border border-orange-500/30 text-[9px] font-bold text-orange-300">
                        DEMO
                      </span>
                    )}
                    {p.description && (
                      <p className="text-2xs text-slate-500 mt-0.5 max-w-lg">{p.description}</p>
                    )}
                  </td>
                  <td className="td text-xs text-slate-400">{p.site || '—'}</td>
                  <td className="td text-xs text-slate-400">{p.panel || '—'}</td>
                  <td className="td text-xs text-slate-400">
                    {p.nominal_voltage_v ? `${p.nominal_voltage_v} V` : '—'}
                    {p.nominal_frequency_hz ? ` / ${p.nominal_frequency_hz} Hz` : ''}
                    {p.control_voltage_v ? ` · ctrl ${p.control_voltage_v} V` : ''}
                  </td>
                  <td className="td text-2xs text-slate-500">
                    {formatDateTime((p as Project & { created_at?: string }).created_at)}
                  </td>
                  <td className="td">
                    <button className="btn py-1" onClick={() => setDuplicating(p)}>
                      <Copy className="h-3 w-3" /> Duplicate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>

      <SafetyNotice tone="info">
        Duplicating a project copies configuration only — controllers, circuit model,
        components, terminals and wires. Measurements, alarms and diagnostic sessions are
        not copied: readings belong to the panel they were taken on, and showing another
        machine's numbers against this one would be actively misleading. Network addresses
        are cleared so they have to be re-entered.
      </SafetyNotice>

      {creating && (
        <ProjectDialog onClose={() => setCreating(false)}
          onSaved={() => { setCreating(false); void reload() }} />
      )}
      {duplicating && (
        <DuplicateDialog project={duplicating} onClose={() => setDuplicating(null)}
          onSaved={() => { setDuplicating(null); void reload() }} />
      )}
    </div>
  )
}

function ProjectDialog({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    name: '', site: '', panel: '', description: '',
    nominal_voltage_v: '', nominal_frequency_hz: '', control_voltage_v: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/projects', {
        ...form,
        nominal_voltage_v: form.nominal_voltage_v ? Number(form.nominal_voltage_v) : null,
        nominal_frequency_hz: form.nominal_frequency_hz
          ? Number(form.nominal_frequency_hz) : null,
        control_voltage_v: form.control_voltage_v ? Number(form.control_voltage_v) : null,
      })
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  return (
    <Dialog title="New project" onClose={onClose} onSubmit={submit} busy={busy}>
      <Field label="Project name" required>
        <input className="input" required value={form.name} placeholder="e.g. PPU34"
          onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Site">
          <input className="input" value={form.site}
            onChange={(e) => setForm({ ...form, site: e.target.value })} />
        </Field>
        <Field label="Panel">
          <input className="input" value={form.panel}
            onChange={(e) => setForm({ ...form, panel: e.target.value })} />
        </Field>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Nominal voltage (V)">
          <input className="input" type="number" step="any" value={form.nominal_voltage_v}
            onChange={(e) => setForm({ ...form, nominal_voltage_v: e.target.value })} />
        </Field>
        <Field label="Frequency (Hz)">
          <input className="input" type="number" step="any" value={form.nominal_frequency_hz}
            onChange={(e) => setForm({ ...form, nominal_frequency_hz: e.target.value })} />
        </Field>
        <Field label="Control voltage (V)">
          <input className="input" type="number" step="any" value={form.control_voltage_v}
            onChange={(e) => setForm({ ...form, control_voltage_v: e.target.value })} />
        </Field>
      </div>
      <Field label="Description">
        <textarea className="input h-20" value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </Field>
      {error && <ErrorNote error={error} />}
    </Dialog>
  )
}

function DuplicateDialog({ project, onClose, onSaved }: {
  project: Project; onClose: () => void; onSaved: () => void
}) {
  const [name, setName] = useState(`${project.name} copy`)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post(`/api/projects/${project.id}/duplicate?name=${encodeURIComponent(name)}`)
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  return (
    <Dialog title={`Duplicate ${project.name}`} onClose={onClose} onSubmit={submit} busy={busy}>
      <Field label="New project name" required>
        <input className="input" required value={name}
          onChange={(e) => setName(e.target.value)} />
      </Field>
      <SafetyNotice tone="info">
        Configuration is copied and polling is left disabled on the new controllers. Host
        addresses are cleared — enter the new panel's actual network settings before enabling
        polling, or you will be reading the original panel.
      </SafetyNotice>
      {error && <ErrorNote error={error} />}
    </Dialog>
  )
}

function Dialog({ title, onClose, onSubmit, busy, children }: {
  title: string; onClose: () => void; onSubmit: (e: React.FormEvent) => void
  busy: boolean; children: React.ReactNode
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
      onClick={onClose}>
      <form className="panel w-full max-w-lg" onClick={(e) => e.stopPropagation()}
        onSubmit={onSubmit}>
        <div className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider">{title}</h2>
        </div>
        <div className="p-4 space-y-3">{children}</div>
        <div className="px-4 py-3 border-t border-edge flex justify-end gap-2">
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>
            {busy ? 'Saving…' : 'Save'}
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
