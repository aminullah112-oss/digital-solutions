import { useEffect, useRef, useState } from 'react'
import { Binary, CheckCircle2, FileUp, Upload } from 'lucide-react'
import { api, getToken } from '@/lib/api'
import { apiUrl } from '@/lib/config'
import { useApi, useSelectedProject } from '@/lib/hooks'
import { formatDateTime } from '@/lib/format'
import { Empty, ErrorNote, Panel, SafetyNotice, Spinner } from '@/components/ui'

interface SchematicRow {
  id: number; name: string; drawing_number: string; revision: string
  original_filename: string; content_type: string; page_count: number
  import_status: string; created_at: string
}

interface Attachment { kind: string; key: string }

interface Proposal {
  kind: string
  key: string
  payload: {
    wire_number?: string | null
    attachments?: Attachment[]
    conflicting_wire_numbers?: string[]
    from_terminal?: string
    to_terminal?: string
    [k: string]: unknown
  }
  confidence: number
  confidence_band: 'HIGH' | 'MEDIUM' | 'LOW'
  page_number: number
  basis: string
  geometry?: { bbox?: number[] } | null
}

interface ImportPage {
  page_number: number
  width?: number
  height?: number
  is_vector?: boolean
  words?: number
  segments?: number
  conductors?: number
  devices?: number
  junction_dots?: number
  characters: number
  has_text: boolean
  note?: string
}

interface NetSummary {
  nets: number
  labelled_nets: number
  nets_with_two_endpoints: number
  orphan_fragments: number
  nets_with_conflicting_numbers: number
  note: string
}

interface ImportResult {
  schematic_id: number
  pages: ImportPage[]
  proposals: Proposal[]
  counts: Record<string, number>
  log: Array<{ stage: string; status: string; detail: string }>
  nets: Record<string, NetSummary>
  note: string
}

// Review order: traced conductors carry the connectivity and deserve the most
// scrutiny, then the things they land on. A flagged conductor sorts to the very
// top — it is the one most likely to be wrong.
const KIND_ORDER: Record<string, number> = {
  net: 0, connection: 1, component: 2, terminal: 3, wire: 4,
}

function byReviewPriority(a: Proposal, b: Proposal): number {
  const aFlagged = (a.payload.conflicting_wire_numbers ?? []).length > 0
  const bFlagged = (b.payload.conflicting_wire_numbers ?? []).length > 0
  if (aFlagged !== bFlagged) return aFlagged ? -1 : 1
  const order = (KIND_ORDER[a.kind] ?? 9) - (KIND_ORDER[b.kind] ?? 9)
  if (order !== 0) return order
  return a.key.localeCompare(b.key)
}

const BAND_CLASS = {
  HIGH: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10',
  MEDIUM: 'text-amber-300 border-amber-500/40 bg-amber-500/10',
  LOW: 'text-red-300 border-red-500/40 bg-red-500/10',
}

export function Schematics() {
  const [projectId] = useSelectedProject()
  const { data, reload } = useApi<SchematicRow[]>(
    projectId ? `/api/schematics?project_id=${projectId}` : null)
  const { data: caps } = useApi<{ stages: Record<string, string>; accepted_types: string[]
    note: string }>('/api/schematics/capabilities')

  const [result, setResult] = useState<ImportResult | null>(null)
  const [accepted, setAccepted] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState<SchematicRow | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (!projectId) return <Empty icon={Binary} title="Select a project" />

  const upload = async (file: File) => {
    setBusy(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('project_id', String(projectId))
      form.append('name', file.name)
      const body = await api.upload<ImportResult>('/api/schematics/upload', form)
      setResult(body)
      // Pre-select HIGH-confidence items only, and never anything the tracer
      // itself flagged as ambiguous. Everything else is an explicit decision
      // by whoever knows the panel.
      setAccepted(new Set(body.proposals
        .filter((p) => p.confidence_band === 'HIGH'
          && !(p.payload.conflicting_wire_numbers ?? []).length)
        .map((p) => `${p.kind}:${p.key}`)))
      void reload()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }

  const commit = async () => {
    if (!result) return
    setBusy(true)
    try {
      const chosen = result.proposals.filter((p) => accepted.has(`${p.kind}:${p.key}`))
      await api.post(`/api/schematics/${result.schematic_id}/accept`, chosen)
      setResult(null)
      setAccepted(new Set())
      void reload()
    } finally { setBusy(false) }
  }

  return (
    <div className="space-y-4">
      <SafetyNotice>
        The original drawing is the authority. This importer reads text — designators,
        terminal tags, wire numbers — and proposes a circuit model from it. It does not
        recognise symbols and does not trace drawn lines, so connectivity that exists only
        as a line on the page will not appear. Review every proposal against the drawing
        before using the circuit model to troubleshoot.
      </SafetyNotice>

      <div className="grid lg:grid-cols-[1fr_320px] gap-4 items-start">
        <Panel
          title="Schematics"
          actions={
            <>
              <input ref={fileRef} type="file" className="hidden"
                accept=".pdf,.png,.jpg,.jpeg,.svg"
                onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])} />
              <button className="btn btn-primary" disabled={busy}
                onClick={() => fileRef.current?.click()}>
                <Upload className="h-3.5 w-3.5" />
                {busy ? 'Analysing…' : 'Upload drawing'}
              </button>
            </>
          }
          dense
        >
          {error && <div className="p-3"><ErrorNote error={error} /></div>}
          {!data?.length ? (
            <Empty icon={FileUp} title="No schematics uploaded"
              hint="PDF, PNG, JPG or SVG." />
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Name</th>
                  <th className="th">Drawing</th>
                  <th className="th">Pages</th>
                  <th className="th">Status</th>
                  <th className="th">Uploaded</th>
                  <th className="th w-px" />
                </tr>
              </thead>
              <tbody>
                {data.map((s) => (
                  <tr key={s.id} className="table-row">
                    <td className="td text-slate-100">{s.name}</td>
                    <td className="td text-xs text-slate-400">
                      {s.drawing_number || '—'} {s.revision}
                    </td>
                    <td className="td text-xs">{s.page_count}</td>
                    <td className="td text-xs text-slate-400">{s.import_status}</td>
                    <td className="td text-2xs text-slate-500">
                      {formatDateTime(s.created_at)}
                    </td>
                    <td className="td">
                      <button className="btn py-1" onClick={() => setViewing(s)}>
                        Original
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>

        <Panel title="Import pipeline">
          <ul className="space-y-1.5">
            {caps && Object.entries(caps.stages).map(([stage, status]) => (
              <li key={stage} className="flex items-start gap-2 text-2xs">
                <span className={`mt-1 h-1.5 w-1.5 rounded-full shrink-0 ${
                  status === 'AVAILABLE' ? 'bg-emerald-500'
                  : status.startsWith('NOT IMPLEMENTED') ? 'bg-slate-600'
                  : 'bg-amber-500'}`} />
                <div>
                  <span className="text-slate-300">{stage.replace(/_/g, ' ')}</span>
                  {status !== 'AVAILABLE' && (
                    <span className="block text-slate-600">{status}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      {result && (
        <>
          <Panel title="What was read from the drawing">
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {result.pages.map((page) => {
                const summary = result.nets[String(page.page_number)]
                return (
                  <div key={page.page_number}
                    className="rounded border border-edge bg-panel-900/60 p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-semibold text-slate-100">
                        Page {page.page_number}
                      </span>
                      <span className={`text-[10px] font-bold ${page.is_vector
                        ? 'text-emerald-300' : 'text-amber-300'}`}>
                        {page.is_vector ? 'VECTOR' : 'NO LINE GEOMETRY'}
                      </span>
                    </div>
                    {page.is_vector ? (
                      <dl className="grid grid-cols-2 gap-y-1 text-2xs">
                        <Stat label="Conductor segments" value={page.conductors} />
                        <Stat label="Device outlines" value={page.devices} />
                        <Stat label="Junction dots" value={page.junction_dots} />
                        <Stat label="Text runs" value={page.words} />
                        {summary && <>
                          <Stat label="Traced conductors" value={summary.nets} />
                          <Stat label="With a wire number" value={summary.labelled_nets} />
                        </>}
                      </dl>
                    ) : (
                      <p className="text-2xs text-amber-200/80">{page.note}</p>
                    )}
                    {summary && summary.nets_with_conflicting_numbers > 0 && (
                      <p className="text-2xs text-amber-300 mt-2">
                        {summary.nets_with_conflicting_numbers} conductor(s) carry more than
                        one wire number — check these first.
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
            <SafetyNotice tone="info">
              Crossing conductors are joined only where a junction dot is drawn, or where one
              ends on the other. Two wires that merely cross are left unconnected, because
              that is what the drawing means. Device symbols break the conductor, so a fuse
              or a coil stays a component between two wires rather than dissolving into one.
            </SafetyNotice>
          </Panel>

          <Panel
            title={`Review proposals — ${accepted.size} of ${result.proposals.length} selected`}
            actions={
              <>
                <button className="btn" onClick={() => setAccepted(new Set(
                  result.proposals.filter((p) => p.confidence_band === 'HIGH')
                    .map((p) => `${p.kind}:${p.key}`)))}>
                  High only
                </button>
                <button className="btn" onClick={() => setAccepted(new Set(
                  result.proposals.filter((p) => p.confidence_band !== 'LOW')
                    .map((p) => `${p.kind}:${p.key}`)))}>
                  High + medium
                </button>
                <button className="btn" onClick={() => setAccepted(new Set())}>Clear</button>
                <button className="btn btn-primary" disabled={busy || accepted.size === 0}
                  onClick={() => void commit()}>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Accept into circuit model
                </button>
              </>
            }
            dense
          >
            <p className="px-4 py-2 text-2xs text-slate-500 border-b border-edge">
              {result.note}
            </p>
            <div className="max-h-[32rem] overflow-y-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th w-px" />
                    <th className="th">Kind</th>
                    <th className="th">Item</th>
                    <th className="th">Lands on</th>
                    <th className="th">Confidence</th>
                    <th className="th">Read from the drawing</th>
                  </tr>
                </thead>
                <tbody>
                  {[...result.proposals].sort(byReviewPriority).map((p) => {
                    const id = `${p.kind}:${p.key}`
                    const conflicts = p.payload.conflicting_wire_numbers ?? []
                    const attachments = p.payload.attachments ?? []
                    return (
                      <tr key={id} className={`table-row ${conflicts.length
                        ? 'bg-amber-950/20' : ''}`}>
                        <td className="td">
                          <input type="checkbox" checked={accepted.has(id)}
                            onChange={(e) => setAccepted((prev) => {
                              const next = new Set(prev)
                              if (e.target.checked) next.add(id)
                              else next.delete(id)
                              return next
                            })} />
                        </td>
                        <td className="td text-2xs uppercase text-slate-500">
                          {p.kind === 'net' ? 'conductor' : p.kind}
                        </td>
                        <td className="td font-mono text-xs text-slate-100">
                          {p.kind === 'connection'
                            ? `${p.payload.from_terminal} ↔ ${p.payload.to_terminal}`
                            : p.key}
                          {conflicts.length > 0 && (
                            <div className="text-[10px] text-amber-300 font-sans mt-0.5">
                              also numbered {conflicts.filter((w) => w !== p.key).join(', ')}
                            </div>
                          )}
                        </td>
                        <td className="td">
                          {attachments.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {attachments.map((a) => (
                                <span key={a.key} className={`px-1.5 py-0.5 rounded border
                                  text-[10px] font-mono ${a.kind === 'terminal'
                                    ? 'border-blue-500/40 bg-blue-500/10 text-blue-200'
                                    : 'border-violet-500/40 bg-violet-500/10 text-violet-200'}`}>
                                  {a.key}
                                </span>
                              ))}
                            </div>
                          ) : <span className="text-slate-700">—</span>}
                        </td>
                        <td className="td">
                          <span className={`px-1.5 py-0.5 rounded border text-[10px] font-bold
                            ${BAND_CLASS[p.confidence_band]}`}>
                            {p.confidence_band} {Math.round(p.confidence * 100)}%
                          </span>
                        </td>
                        <td className="td text-2xs text-slate-500 max-w-md">
                          {p.basis}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="px-4 py-2 border-t border-edge">
              {result.log.map((entry, i) => (
                <p key={i} className="text-2xs text-slate-600">
                  <span className="font-semibold text-slate-500">{entry.stage}</span>
                  {' — '}
                  <span className={entry.status === 'OK' ? 'text-emerald-400/70'
                    : entry.status === 'UNAVAILABLE' ? 'text-amber-400/70' : ''}>
                    {entry.status}
                  </span>
                  : {entry.detail}
                </p>
              ))}
            </div>
          </Panel>
        </>
      )}

      {viewing && (
        <OriginalViewer schematic={viewing} onClose={() => setViewing(null)} />
      )}
    </div>
  )
}

/**
 * Side-by-side is the whole point: the interactive model on the left in
 * Circuit Explorer, the untouched drawing here. A derived model that can't be
 * checked against the source is not trustworthy.
 */
function Stat({ label, value }: { label: string; value: number | undefined }) {
  return (
    <>
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-200 tnum text-right">{value ?? '—'}</dd>
    </>
  )
}

function OriginalViewer({ schematic, onClose }: {
  schematic: SchematicRow; onClose: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = getToken()
    let objectUrl: string | null = null
    fetch(apiUrl(`/api/schematics/${schematic.id}/original`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.blob())
      .then((b) => {
        objectUrl = URL.createObjectURL(b)
        setUrl(objectUrl)
      })
      .finally(() => setLoading(false))
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [schematic.id])

  return (
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-6"
      onClick={onClose}>
      <div className="panel w-full max-w-5xl h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider">
            Original drawing — {schematic.name}
          </h2>
          <button className="btn py-1" onClick={onClose}>Close</button>
        </div>
        <div className="flex-1 bg-white/5 overflow-hidden">
          {loading ? <Spinner /> : url ? (
            <iframe src={url} title={schematic.name} className="w-full h-full" />
          ) : (
            <Empty title="Could not load the original file" />
          )}
        </div>
      </div>
    </div>
  )
}
