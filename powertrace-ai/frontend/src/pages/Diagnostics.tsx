import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Play, Stethoscope, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useSelectedProject } from '@/lib/hooks'
import type { Discontinuity, FaultTreeNode, Finding, DiagnosticSession } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import {
  Confidence, Empty, ErrorNote, Panel, SafetyNotice, SourceBadge, Spinner,
} from '@/components/ui'
import { FaultTree } from '@/components/FaultTree'

interface Evaluation {
  findings: Finding[]
  discontinuities: Discontinuity[]
  coverage: {
    nodes_in_scope: number; measured: number; unmeasured: number
    coverage_pct: number; unmeasured_keys: string[]; note: string
  }
  fault_tree: FaultTreeNode
  generated_at: string
}

const FAULT_CATEGORIES = [
  'BREAKER_FAIL_TO_CLOSE', 'BREAKER_FAIL_TO_OPEN', 'CONTROL_POWER',
  'COMMUNICATION', 'GENERAL',
]

export function Diagnostics() {
  const [projectId] = useSelectedProject()
  const [category, setCategory] = useState('BREAKER_FAIL_TO_CLOSE')
  const navigate = useNavigate()

  const { data, error, loading, reload } = useApi<Evaluation>(
    projectId ? `/api/diagnostics/evaluate/${projectId}?fault_category=${category}` : null,
    [category])
  const { data: sessions } = useApi<DiagnosticSession[]>(
    projectId ? `/api/diagnostics?project_id=${projectId}` : null)

  const [creating, setCreating] = useState(false)

  const openSession = async () => {
    if (!projectId) return
    setCreating(true)
    try {
      const session = await api.post<DiagnosticSession>('/api/diagnostics', {
        project_id: projectId,
        title: category.replace(/_/g, ' ').toLowerCase()
          .replace(/^\w/, (c) => c.toUpperCase()),
        fault_category: category,
        symptom: '',
      })
      navigate(`/diagnostics/${session.id}`)
    } finally {
      setCreating(false)
    }
  }

  if (!projectId) return <Empty icon={Stethoscope} title="Select a project" />
  if (loading && !data) return <Spinner label="Running deterministic analysis…" />

  return (
    <div className="space-y-4">
      {error && <ErrorNote error={error} onRetry={reload} />}

      <div className="flex items-center gap-2 flex-wrap">
        <select className="input w-auto" value={category}
          onChange={(e) => setCategory(e.target.value)}>
          {FAULT_CATEGORIES.map((c) => (
            <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <button className="btn" onClick={() => void reload()}>
          <Play className="h-3.5 w-3.5" /> Re-run analysis
        </button>
        <button className="btn btn-primary" onClick={() => void openSession()} disabled={creating}>
          <Stethoscope className="h-3.5 w-3.5" />
          {creating ? 'Opening…' : 'Open diagnostic session'}
        </button>
        {data && (
          <span className="ml-auto text-2xs text-slate-500">
            Evaluated {formatDateTime(data.generated_at)}
          </span>
        )}
      </div>

      {data && (
        <>
          <div className="grid lg:grid-cols-2 gap-4">
            <Panel title="Measured discontinuities">
              {data.discontinuities.length === 0 ? (
                <p className="text-xs text-slate-500">
                  No pair of measurements brackets a break in this circuit. Taking a
                  measurement at each end of a suspect segment is what makes this section
                  useful — it is not inferred from controller state.
                </p>
              ) : (
                <div className="space-y-3">
                  {data.discontinuities.map((d, i) => (
                    <div key={i} className="rounded border border-red-700/40 bg-red-950/20 p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Zap className="h-3.5 w-3.5 text-red-400" />
                        <span className="text-xs font-mono text-slate-100">
                          {d.between[0]} → {d.between[1]}
                        </span>
                        <Confidence level={d.confidence} />
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">{d.statement}</p>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-2xs">
                        <div>
                          <span className="label">Upstream</span>
                          <div className="text-emerald-300 value">
                            {d.upstream_measured?.value} {d.upstream_measured?.unit}
                          </div>
                          <SourceBadge source={d.upstream_measured?.source}
                            quality={d.upstream_measured?.quality} />
                        </div>
                        <div>
                          <span className="label">Downstream</span>
                          <div className="text-red-300 value">
                            {d.downstream_measured?.value} {d.downstream_measured?.unit}
                          </div>
                          <SourceBadge source={d.downstream_measured?.source}
                            quality={d.downstream_measured?.quality} />
                        </div>
                      </div>
                      {d.components_in_segment.length > 0 && (
                        <p className="mt-2 text-2xs text-slate-500">
                          In the segment: {d.components_in_segment
                            .map((c) => c.label || c.key).join(' · ')}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Panel>

            <Panel title="Fault tree">
              <FaultTree node={data.fault_tree} />
            </Panel>
          </div>

          <Panel title={`Findings (${data.findings.length})`}>
            {data.findings.length === 0 ? (
              <p className="text-xs text-slate-500">
                No rule conditions are currently met.
              </p>
            ) : (
              <div className="space-y-3">
                {data.findings.map((f) => (
                  <div key={f.rule_key} className="rounded border border-edge bg-panel-900/60 p-3">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-xs font-semibold text-slate-100">{f.title}</span>
                      <Confidence level={f.confidence} />
                      <span className="ml-auto font-mono text-[10px] text-slate-600">
                        {f.rule_key}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">{f.statement}</p>

                    {f.evidence.length > 0 && (
                      <div className="mt-2">
                        <span className="label">Evidence</span>
                        <ul className="mt-1 space-y-1">
                          {f.evidence.map((e, i) => (
                            <li key={i} className="flex items-center gap-2 text-2xs">
                              <SourceBadge source={e.source as never}
                                quality={e.quality as never} />
                              <span className="text-slate-300">{e.label}</span>
                              <span className="text-slate-500 font-mono">
                                {String(e.value)}
                              </span>
                              <span className="text-slate-600 truncate">{e.detail}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {f.recommended_test && (
                      <div className="mt-2 rounded bg-blue-950/20 border border-blue-800/30
                        px-2.5 py-1.5">
                        <span className="label text-blue-400">Recommended test</span>
                        <p className="text-xs text-blue-100 mt-0.5">{f.recommended_test}</p>
                      </div>
                    )}

                    {f.missing_information.length > 0 && (
                      <div className="mt-2">
                        <span className="label text-amber-400">Missing information</span>
                        <ul className="mt-0.5 list-disc list-inside text-2xs text-amber-200/80">
                          {f.missing_information.map((m, i) => <li key={i}>{m}</li>)}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Measurement coverage">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="h-2 rounded bg-panel-700 overflow-hidden">
                  <div className="h-full bg-emerald-500"
                    style={{ width: `${data.coverage.coverage_pct}%` }} />
                </div>
              </div>
              <span className="text-sm value text-slate-200">
                {data.coverage.measured}/{data.coverage.nodes_in_scope}
              </span>
              <span className="text-xs text-slate-500">
                {data.coverage.coverage_pct}% measured
              </span>
            </div>
            <p className="text-2xs text-slate-500 mt-2">{data.coverage.note}</p>
          </Panel>
        </>
      )}

      {sessions && sessions.length > 0 && (
        <Panel title="Diagnostic sessions" dense>
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">#</th>
                <th className="th">Title</th>
                <th className="th">Category</th>
                <th className="th">Status</th>
                <th className="th">Technician</th>
                <th className="th">Opened</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="table-row">
                  <td className="td font-mono text-xs text-slate-500">{s.id}</td>
                  <td className="td">
                    <Link to={`/diagnostics/${s.id}`}
                      className="text-slate-100 hover:text-blue-300">{s.title}</Link>
                  </td>
                  <td className="td text-xs text-slate-400">
                    {s.fault_category.replace(/_/g, ' ')}
                  </td>
                  <td className="td text-xs">{s.status}</td>
                  <td className="td text-xs text-slate-400">{s.technician}</td>
                  <td className="td text-2xs text-slate-500">{formatDateTime(s.opened_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}

      <SafetyNotice>
        Findings are analysis, not verdicts. A finding is only stated as CONFIRMED BY
        MEASUREMENT when physical measurements support it on both sides. Everything else is
        LIKELY, POSSIBLE or UNVERIFIED and needs a measurement to settle.
      </SafetyNotice>
    </div>
  )
}
