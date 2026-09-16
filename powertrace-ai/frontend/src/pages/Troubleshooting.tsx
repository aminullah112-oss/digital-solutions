import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Brain, CheckCircle2, CircleDashed, FileText, RefreshCw, Wrench, XCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useSelectedProject } from '@/lib/hooks'
import type { DiagnosticSession, DiagnosticStep, FaultTreeNode } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import {
  Confidence, Empty, ErrorNote, Panel, SafetyNotice, SourceBadge, Spinner,
} from '@/components/ui'
import { FaultTree } from '@/components/FaultTree'

const STEP_ICON = {
  PASS: { icon: CheckCircle2, color: 'text-emerald-400' },
  FAIL: { icon: XCircle, color: 'text-red-400' },
  MARGINAL: { icon: CircleDashed, color: 'text-amber-400' },
  PENDING: { icon: CircleDashed, color: 'text-slate-600' },
  INFO: { icon: CircleDashed, color: 'text-blue-400' },
  SKIPPED: { icon: CircleDashed, color: 'text-slate-700' },
} as const

export function Troubleshooting() {
  const { sessionId } = useParams()
  const [projectId] = useSelectedProject()
  const navigate = useNavigate()
  const { data: sessions } = useApi<DiagnosticSession[]>(
    !sessionId && projectId ? `/api/diagnostics?project_id=${projectId}` : null)
  const { data: session, error, loading, reload } = useApi<DiagnosticSession>(
    sessionId ? `/api/diagnostics/${sessionId}` : null)
  const { data: tree } = useApi<FaultTreeNode>(
    sessionId ? `/api/diagnostics/${sessionId}/fault-tree` : null, [session?.findings.length])

  const [busy, setBusy] = useState<string | null>(null)

  if (!sessionId) {
    if (!projectId) return <Empty icon={Wrench} title="Select a project" />
    if (!sessions?.length) {
      return <Empty icon={Wrench} title="No diagnostic sessions"
        hint="Open one from Diagnostics to generate a troubleshooting procedure." />
    }
    return (
      <Panel title="Open a session" dense>
        <div className="divide-y divide-edge/60">
          {sessions.map((s) => (
            <button key={s.id} className="w-full text-left px-4 py-3 hover:bg-panel-700/40"
              onClick={() => navigate(`/diagnostics/${s.id}`)}>
              <div className="text-sm text-slate-100">{s.title}</div>
              <div className="text-2xs text-slate-500">
                #{s.id} · {s.status} · {formatDateTime(s.opened_at)}
              </div>
            </button>
          ))}
        </div>
      </Panel>
    )
  }

  if (loading && !session) return <Spinner />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!session) return null

  const refresh = async () => {
    setBusy('refresh')
    try {
      await api.post(`/api/diagnostics/${session.id}/refresh`)
      await reload()
    } finally { setBusy(null) }
  }

  const runAi = async () => {
    setBusy('ai')
    try {
      await api.post(`/api/diagnostics/${session.id}/ai`)
      await reload()
    } finally { setBusy(null) }
  }

  const makeReport = async () => {
    setBusy('report')
    try {
      const created = await api.post<{ id: number }>('/api/reports', {
        project_id: session.project_id,
        diagnostic_session_id: session.id,
        technician: session.technician,
      })
      navigate(`/reports?open=${created.id}`)
    } finally { setBusy(null) }
  }

  const done = session.steps.filter((s) => s.status !== 'PENDING').length

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-4 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">{session.title}</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Session #{session.id} · {session.fault_category.replace(/_/g, ' ')} ·
            opened {formatDateTime(session.opened_at)} · {session.technician}
          </p>
          {session.symptom && (
            <p className="text-xs text-slate-400 mt-1">{session.symptom}</p>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button className="btn" onClick={() => void refresh()} disabled={busy !== null}>
            <RefreshCw className="h-3.5 w-3.5" />
            {busy === 'refresh' ? 'Re-evaluating…' : 'Re-evaluate with current data'}
          </button>
          <button className="btn" onClick={() => void runAi()} disabled={busy !== null}>
            <Brain className="h-3.5 w-3.5" />
            {busy === 'ai' ? 'Analysing…' : 'Run AI analysis'}
          </button>
          <button className="btn btn-primary" onClick={() => void makeReport()}
            disabled={busy !== null}>
            <FileText className="h-3.5 w-3.5" /> Generate report
          </button>
        </div>
      </div>

      <div className="grid lg:grid-cols-[1fr_380px] gap-4 items-start">
        <Panel
          title={`Procedure — ${done}/${session.steps.length} steps completed`}
          dense
        >
          {session.steps.length === 0 ? (
            <Empty title="No procedure generated"
              hint="Import a schematic so the engine can produce circuit-specific steps." />
          ) : (
            <ol className="divide-y divide-edge/60">
              {session.steps.map((step) => (
                <StepRow key={step.id} step={step} onChanged={reload} />
              ))}
            </ol>
          )}
        </Panel>

        <div className="space-y-4">
          {tree && (
            <Panel title="Fault tree">
              <FaultTree node={tree} />
            </Panel>
          )}

          <Panel title={`Findings (${session.findings.length})`}>
            {session.findings.length === 0 ? (
              <p className="text-xs text-slate-500">No rule conditions met.</p>
            ) : (
              <div className="space-y-2.5">
                {session.findings.map((f) => (
                  <div key={f.rule_key} className="rounded border border-edge
                    bg-panel-900/60 p-2.5">
                    <div className="flex items-center gap-2 mb-1">
                      <Confidence level={f.confidence} />
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">{f.statement}</p>
                    {f.recommended_test && (
                      <p className="text-2xs text-blue-300 mt-1.5">{f.recommended_test}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {session.ai_analysis && <AiPanel analysis={session.ai_analysis} />}
        </div>
      </div>

      <SafetyNotice>
        Every measurement step assumes appropriately rated test equipment and site safety
        procedures. This procedure does not authorise any switching, and nothing in it
        establishes that a circuit is de-energized.
      </SafetyNotice>
    </div>
  )
}

function StepRow({ step, onChanged }: { step: DiagnosticStep; onChanged: () => void }) {
  const [notes, setNotes] = useState(step.notes)
  const [saving, setSaving] = useState(false)
  const meta = STEP_ICON[step.status] ?? STEP_ICON.PENDING
  const Icon = meta.icon

  const save = async (status?: string) => {
    setSaving(true)
    try {
      await api.patch(`/api/diagnostics/steps/${step.id}`, { notes, status })
      onChanged()
    } finally { setSaving(false) }
  }

  return (
    <li className="px-4 py-3">
      <div className="flex items-start gap-3">
        <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${meta.color}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-2xs text-slate-600 font-mono">
              STEP {String(step.sequence).padStart(2, '0')}
            </span>
            <span className="text-sm text-slate-100 font-medium">{step.title}</span>
            <span className={`text-[10px] font-bold ${meta.color}`}>{step.status}</span>
            {step.circuit_node_key && (
              <span className="text-[10px] font-mono text-slate-600">
                {step.circuit_node_key}
              </span>
            )}
          </div>

          <p className="text-xs text-slate-400 mt-1 leading-relaxed">{step.instruction}</p>

          <div className="grid sm:grid-cols-2 gap-2 mt-2">
            <ValueBox title="Expected" payload={step.expected} />
            <ValueBox title="Actual" payload={step.actual} />
          </div>

          {step.next_action && (
            <p className="text-2xs text-slate-500 mt-2">
              <span className="text-slate-600 font-semibold">NEXT: </span>
              {step.next_action}
            </p>
          )}

          {step.safety_notice && (
            <p className="text-2xs text-amber-300/90 mt-1.5">{step.safety_notice}</p>
          )}

          <div className="flex items-center gap-2 mt-2">
            <input
              className="input py-1 text-xs flex-1"
              placeholder="Technician notes…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={() => notes !== step.notes && void save()}
            />
            <button className="btn py-1" disabled={saving} onClick={() => void save('PASS')}>
              Pass
            </button>
            <button className="btn py-1" disabled={saving} onClick={() => void save('FAIL')}>
              Fail
            </button>
          </div>
        </div>
      </div>
    </li>
  )
}

function ValueBox({ title, payload }: { title: string
  payload: Record<string, unknown> | null }) {
  const value = payload?.value
  const description = payload?.description as string | undefined
  return (
    <div className="rounded border border-edge bg-panel-900/60 px-2.5 py-1.5">
      <div className="flex items-center justify-between">
        <span className="label">{title}</span>
        {payload?.source ? (
          <SourceBadge source={payload.source as never} quality={payload.quality as never} />
        ) : null}
      </div>
      <div className="text-xs text-slate-200 value mt-0.5">
        {value !== undefined && value !== null
          ? `${value}${payload?.unit ? ` ${payload.unit}` : ''}`
          : description ?? <span className="text-slate-600">—</span>}
      </div>
      {payload?.note ? (
        <p className="text-[10px] text-slate-600 mt-0.5">{String(payload.note)}</p>
      ) : null}
    </div>
  )
}

function AiPanel({ analysis }: { analysis: Record<string, any> }) {
  if (analysis.status !== 'OK') {
    return (
      <Panel title="AI analysis">
        <p className="text-xs text-slate-400">{analysis.reason}</p>
        <p className="text-2xs text-slate-600 mt-2">
          The deterministic findings above do not depend on the AI layer.
        </p>
      </Panel>
    )
  }
  return (
    <Panel title="AI analysis" actions={<Confidence level={analysis.confidence} />}>
      <div className="space-y-2.5 text-xs">
        <Section label="Problem" body={analysis.problem_summary} />
        {(analysis.possible_fault_areas ?? []).length > 0 && (
          <div>
            <span className="label">Possible fault areas</span>
            <ul className="mt-1 space-y-1.5">
              {analysis.possible_fault_areas.map((area: any, i: number) => (
                <li key={i} className="rounded border border-edge bg-panel-900/60 px-2.5 py-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-slate-200">{area.area}</span>
                    {area.confidence && <Confidence level={area.confidence} />}
                  </div>
                  <p className="text-slate-400 mt-0.5">{area.reasoning}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
        <Section label="Recommended test" body={analysis.recommended_test} />
        <Section label="Expected result" body={analysis.expected_result} />
        <Section label="Observed result" body={analysis.observed_result} />
        <Section label="Next step" body={analysis.next_step} />

        {(analysis.missing_information ?? []).length > 0 && (
          <div>
            <span className="label text-amber-400">Missing information</span>
            <ul className="list-disc list-inside text-2xs text-amber-200/80 mt-0.5">
              {analysis.missing_information.map((m: string, i: number) => <li key={i}>{m}</li>)}
            </ul>
          </div>
        )}

        <div className={`rounded border px-2.5 py-1.5 text-2xs ${
          analysis.unsupported_values?.length
            ? 'border-red-700/50 bg-red-950/30 text-red-200'
            : 'border-edge bg-panel-900/60 text-slate-500'}`}>
          {analysis.validation_note}
        </div>
      </div>
    </Panel>
  )
}

function Section({ label, body }: { label: string; body?: string }) {
  if (!body) return null
  return (
    <div>
      <span className="label">{label}</span>
      <p className="text-slate-300 leading-relaxed mt-0.5">{body}</p>
    </div>
  )
}
