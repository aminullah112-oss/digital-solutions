import { useState } from 'react'
import { AlertTriangle, Database, KeyRound, ShieldCheck, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { useApi } from '@/lib/hooks'
import {
  Empty, ErrorNote, Panel, SafetyNotice, Spinner, StatusDot,
} from '@/components/ui'

interface SettingsPayload {
  app_name: string; environment: string; demo_mode: boolean
  allow_control_writes: boolean; direct_input_voltage_limit_v: number
  default_poll_interval_ms: number; stale_after_s: number; history_depth: number
  ai_provider: string; ai_model: string | null; database: string
  modbus_timeout_s: number; modbus_retries: number
}

interface RegisterMap {
  id: number; name: string; controller_type: string; manufacturer: string
  model: string; source_document: string; verified: boolean; verified_by: string
  is_simulator_only: boolean; register_count: number
}

interface DemoStatus {
  demo_mode: boolean; project_id: number | null; project_name: string | null
  controllers: Array<{ id: number; name: string; fault_mode: string
    connection_state: string }>
  available_faults: string[]
}

export function SettingsPage() {
  const { data: settings } = useApi<SettingsPayload>('/api/settings')
  const { data: maps } = useApi<RegisterMap[]>('/api/register-maps')
  const { data: demo, reload: reloadDemo } = useApi<DemoStatus>('/api/demo/status')
  const { data: template } = useApi<{ header: string; example_row: string; note: string }>(
    '/api/register-maps/template/csv')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (!settings) return <Spinner />

  const seedDemo = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/demo/seed?reset=true')
      void reloadDemo()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  const injectFault = async (controllerId: number, mode: string) => {
    await api.post(`/api/demo/fault?controller_id=${controllerId}&mode=${mode}`)
    void reloadDemo()
  }

  return (
    <div className="space-y-4">
      {error && <ErrorNote error={error} />}

      <Panel title="Safety policy">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <div>
              <div className="text-sm text-slate-100">Control commands</div>
              <div className="text-xs text-slate-500">
                {settings.allow_control_writes
                  ? 'Flag is on, but no write path exists in any protocol adapter.'
                  : 'Disabled. No adapter implements a write; every write call raises.'}
              </div>
            </div>
            <StatusDot tone="ok" label="READ-ONLY" />
          </div>

          <div className="flex items-center gap-3">
            <Zap className="h-5 w-5 text-amber-400" />
            <div>
              <div className="text-sm text-slate-100">Direct input voltage limit</div>
              <div className="text-xs text-slate-500">
                A measurement channel bound above {settings.direct_input_voltage_limit_v} V must
                declare a rated PT/VT, CT or isolating transducer.
              </div>
            </div>
            <span className="ml-auto value text-slate-200">
              {settings.direct_input_voltage_limit_v} V
            </span>
          </div>
        </div>
      </Panel>

      <div className="grid lg:grid-cols-2 gap-4">
        <Panel title="Runtime configuration">
          <dl className="grid grid-cols-[180px_1fr] gap-y-1.5 text-xs">
            <Row label="Environment" value={settings.environment} />
            <Row label="Database" value={<span className="inline-flex items-center gap-1.5">
              <Database className="h-3 w-3" />{settings.database}</span>} />
            <Row label="Demo mode" value={settings.demo_mode ? 'ON' : 'OFF'} />
            <Row label="Default poll interval" value={`${settings.default_poll_interval_ms} ms`} />
            <Row label="Stale threshold" value={`${settings.stale_after_s} s`} />
            <Row label="Trend buffer depth" value={`${settings.history_depth} samples`} />
            <Row label="Modbus timeout" value={`${settings.modbus_timeout_s} s`} />
            <Row label="Modbus retries" value={settings.modbus_retries} />
            <Row label="AI provider" value={settings.ai_provider === 'none'
              ? 'none — deterministic engine only' : `${settings.ai_provider} / ${settings.ai_model}`} />
          </dl>
          <p className="text-2xs text-slate-600 mt-3">
            These are read from the server's environment. Change them in the backend's .env
            and restart; they are deliberately not editable from the UI.
          </p>
        </Panel>

        <Panel title="Register maps">
          {!maps?.length ? (
            <Empty icon={KeyRound} title="No register maps"
              hint="A controller with no map reads nothing — that is intentional." />
          ) : (
            <div className="space-y-2">
              {maps.map((m) => (
                <div key={m.id} className="rounded border border-edge bg-panel-900/60 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-100">{m.name}</span>
                    <span className="text-2xs text-slate-500">
                      {m.register_count} registers
                    </span>
                    <span className="ml-auto">
                      {m.is_simulator_only ? (
                        <span className="text-[10px] font-bold text-orange-300">
                          SIMULATOR ONLY
                        </span>
                      ) : m.verified ? (
                        <span className="text-[10px] font-bold text-emerald-300">
                          VERIFIED by {m.verified_by}
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold text-amber-300">UNVERIFIED</span>
                      )}
                    </span>
                  </div>
                  {m.source_document && (
                    <p className="text-2xs text-slate-600 mt-0.5">
                      Source: {m.source_document}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {template && (
            <div className="mt-3 rounded border border-edge bg-panel-900 p-3">
              <div className="label mb-1">CSV import template</div>
              <code className="block text-[10px] text-slate-400 font-mono break-all">
                {template.header}
              </code>
              <code className="block text-[10px] text-slate-600 font-mono break-all mt-1">
                {template.example_row}
              </code>
              <p className="text-2xs text-amber-300/80 mt-2">{template.note}</p>
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Demo mode"
        actions={
          <button className="btn btn-primary" onClick={() => void seedDemo()} disabled={busy}>
            {busy ? 'Seeding…' : demo?.project_id ? 'Re-seed demo project' : 'Seed demo project'}
          </button>
        }
      >
        {!settings.demo_mode ? (
          <p className="text-xs text-slate-500">
            Demo mode is disabled in this installation.
          </p>
        ) : (
          <>
            <SafetyNotice>
              <strong>Demo mode produces simulated values.</strong> They are tagged SIMULATED at
              the point of production and stay tagged through every screen, export and report.
              Turn demo mode off on a production installation.
            </SafetyNotice>

            {demo?.controllers.length ? (
              <div className="mt-3 space-y-2">
                {demo.controllers.map((c) => (
                  <div key={c.id} className="flex items-center gap-3 rounded border border-edge
                    bg-panel-900/60 px-3 py-2">
                    <span className="text-xs text-slate-100 w-40">{c.name}</span>
                    <StatusDot
                      tone={c.connection_state === 'ONLINE' ? 'ok' : 'fault'}
                      label={c.connection_state}
                    />
                    <select
                      className="input py-1 text-xs w-auto ml-auto"
                      value={c.fault_mode}
                      onChange={(e) => void injectFault(c.id, e.target.value)}
                    >
                      {demo.available_faults.map((mode) => (
                        <option key={mode} value={mode}>{mode.replace(/_/g, ' ')}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 mt-3">
                No demo project seeded yet.
              </p>
            )}
          </>
        )}
      </Panel>

      <Panel title="Keyboard shortcuts">
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <Shortcut keys="Ctrl K" label="Global search" />
          <Shortcut keys="F" label="Fit schematic to view" />
          <Shortcut keys="T" label="Trace selected circuit" />
          <Shortcut keys="D" label="Open diagnostics" />
          <Shortcut keys="Esc" label="Clear highlight" />
        </dl>
      </Panel>

      <div className="flex items-start gap-2 text-2xs text-slate-600">
        <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
        <p>
          PowerTrace AI is a diagnostic aid. It is not a safety-rated protection system, it
          issues no control commands, and nothing it displays establishes that a circuit is
          de-energized. Verify with appropriately rated test equipment and follow site safety
          procedures.
        </p>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <>
      <dt className="label pt-0.5">{label}</dt>
      <dd className="text-slate-200">{value}</dd>
    </>
  )
}

function Shortcut({ keys, label }: { keys: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <kbd className="px-1.5 py-0.5 rounded bg-panel-900 border border-edge text-[10px]
        text-slate-400">{keys}</kbd>
      <span className="text-slate-400">{label}</span>
    </div>
  )
}
