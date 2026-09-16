import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ReactFlowProvider } from '@xyflow/react'
import {
  ArrowDown, ArrowUp, Cable, Crosshair, Maximize2, Search, Split,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useApi, useKeyboard, useSelectedProject } from '@/lib/hooks'
import type { CircuitEdge, CircuitNode, TerminalStatus } from '@/lib/types'
import { formatDateTime, formatValue } from '@/lib/format'
import {
  Empty, ErrorNote, Panel, SafetyNotice, SourceBadge, Spinner, StatusDot,
} from '@/components/ui'
import { CircuitCanvas } from '@/components/circuit/CircuitCanvas'

interface CircuitPayload {
  project_id: number
  nodes: CircuitNode[]
  edges: CircuitEdge[]
  node_count: number
  edge_count: number
  unverified_nodes: string[]
  unverified_edges: number[]
  status: Record<string, TerminalStatus>
}

interface TracePayload {
  start: string
  direction: string
  nodes: CircuitNode[]
  edges: CircuitEdge[]
  paths: Array<Array<{ key: string; via: CircuitEdge | null }>>
  truncated: boolean
  safety_notice?: string
}

export function CircuitExplorer() {
  const [projectId] = useSelectedProject()
  const [params, setParams] = useSearchParams()
  const { data, error, loading, reload } = useApi<CircuitPayload>(
    projectId ? `/api/circuits/${projectId}` : null)

  const [selected, setSelected] = useState<string | null>(params.get('select'))
  const [trace, setTrace] = useState<TracePayload | null>(null)
  const [highlight, setHighlight] = useState<string[] | null>(null)
  const [query, setQuery] = useState('')
  const [fitSignal, setFitSignal] = useState(0)

  // Refresh status on a timer: the topology is static, live status is not.
  useEffect(() => {
    if (!projectId) return
    const id = setInterval(() => { void reload() }, 4000)
    return () => clearInterval(id)
  }, [projectId, reload])

  const select = useCallback((key: string | null) => {
    setSelected(key)
    if (key) setParams({ select: key })
    else setParams({})
  }, [setParams])

  const runTrace = useCallback(async (direction: 'up' | 'down' | 'both') => {
    if (!projectId || !selected) return
    const result = await api.get<TracePayload>(
      `/api/circuits/${projectId}/trace/${encodeURIComponent(selected)}?direction=${direction}`)
    setTrace(result)
    setHighlight(result.nodes.map((n) => n.key))
  }, [projectId, selected])

  const runHighlight = useCallback(async () => {
    if (!projectId || !selected) return
    const result = await api.get<{ node_keys: string[] }>(
      `/api/circuits/${projectId}/highlight/${encodeURIComponent(selected)}`)
    setHighlight(result.node_keys)
    setTrace(null)
  }, [projectId, selected])

  useKeyboard(useMemo(() => ({
    f: () => setFitSignal((n) => n + 1),
    t: () => { void runTrace('both') },
    escape: () => { setHighlight(null); setTrace(null) },
  }), [runTrace]))

  const status = data?.status ?? {}
  const suspects = useMemo(() => {
    return Object.entries(status)
      .filter(([, s]) => s.overlay_color === 'RED')
      .map(([key]) => key)
  }, [status])

  const searchResults = useMemo(() => {
    if (!query.trim() || !data) return []
    const q = query.trim().toLowerCase()
    return data.nodes.filter((n) =>
      n.key.toLowerCase().includes(q)
      || n.label.toLowerCase().includes(q)
      || n.controller_signal.toLowerCase().includes(q)
      || n.terminal?.tag.toLowerCase().includes(q)
      || n.wire?.wire_number.toLowerCase().includes(q)
      || n.component?.reference_designator.toLowerCase().includes(q)
    ).slice(0, 8)
  }, [query, data])

  if (!projectId) return <Empty icon={Cable} title="Select a project" />
  if (loading && !data) return <Spinner label="Loading circuit model…" />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!data?.nodes.length) {
    return <Empty icon={Cable} title="No circuit model for this project"
      hint="Import a schematic and accept the reviewed proposals, or add nodes manually." />
  }

  const selectedNode = data.nodes.find((n) => n.key === selected)
  const selectedStatus = selected ? status[selected] : undefined

  return (
    <div className="grid grid-cols-[1fr_360px] gap-4 h-[calc(100vh-10rem)]">
      <div className="flex flex-col gap-3 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-500 absolute left-2.5 top-2.5" />
            <input
              className="input pl-8 w-72"
              placeholder="Terminal, component, wire, DO-07…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchResults[0]) {
                  select(searchResults[0].key)
                  setQuery('')
                }
              }}
            />
            {searchResults.length > 0 && (
              <div className="absolute z-20 mt-1 w-72 panel overflow-hidden">
                {searchResults.map((n) => (
                  <button
                    key={n.key}
                    className="w-full text-left px-3 py-1.5 hover:bg-panel-700 text-xs"
                    onClick={() => { select(n.key); setQuery('') }}
                  >
                    <span className="text-slate-100 font-medium">{n.label}</span>
                    <span className="ml-2 text-slate-600 font-mono text-[10px]">{n.key}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button className="btn" disabled={!selected} onClick={() => void runTrace('up')}>
            <ArrowUp className="h-3.5 w-3.5" /> Trace upstream
          </button>
          <button className="btn" disabled={!selected} onClick={() => void runTrace('down')}>
            <ArrowDown className="h-3.5 w-3.5" /> Trace downstream
          </button>
          <button className="btn" disabled={!selected} onClick={() => void runHighlight()}>
            <Split className="h-3.5 w-3.5" /> Highlight circuit
          </button>
          <button className="btn" onClick={() => setFitSignal((n) => n + 1)}>
            <Maximize2 className="h-3.5 w-3.5" /> Fit
            <kbd className="ml-1 text-[9px] text-slate-500">F</kbd>
          </button>
          {highlight && (
            <button className="btn" onClick={() => { setHighlight(null); setTrace(null) }}>
              Clear highlight
              <kbd className="ml-1 text-[9px] text-slate-500">ESC</kbd>
            </button>
          )}

          <div className="ml-auto flex items-center gap-3 text-2xs text-slate-500">
            <span>{data.node_count} nodes · {data.edge_count} edges</span>
            {data.unverified_nodes.length > 0 && (
              <span className="text-amber-400">
                {data.unverified_nodes.length} unverified
              </span>
            )}
          </div>
        </div>

        <div className="flex-1 panel overflow-hidden min-h-0">
          <ReactFlowProvider>
            <CircuitCanvas
              nodes={data.nodes}
              edges={data.edges}
              status={status}
              selectedKey={selected}
              highlightKeys={highlight}
              suspectKeys={suspects}
              onSelect={select}
              fitSignal={fitSignal}
            />
          </ReactFlowProvider>
        </div>

        <Legend />
      </div>

      <div className="overflow-y-auto space-y-3 pr-1">
        {!selectedNode ? (
          <Empty icon={Crosshair} title="Select a node"
            hint="Click a component on the canvas, or search for a tag such as TB23-14." />
        ) : (
          <NodeInspector
            node={selectedNode}
            status={selectedStatus}
            trace={trace}
            onSelect={select}
          />
        )}
      </div>
    </div>
  )
}

function Legend() {
  return (
    <div className="flex items-center gap-4 text-2xs text-slate-500 px-1 flex-wrap">
      <span className="font-semibold text-slate-400">Overlay (from measurement only):</span>
      <StatusDot tone="ok" label="Within expectation" />
      <StatusDot tone="fault" label="Outside expectation" />
      <StatusDot tone="warn" label="Marginal" />
      <StatusDot tone="unknown" label="Not measured" />
      <span className="ml-auto flex items-center gap-3">
        <LegendEdge color="#64748b" label="Power" />
        <LegendEdge color="#3b82f6" label="Signal" dashed />
        <LegendEdge color="#8b5cf6" label="Control" dashed />
        <LegendEdge color="#f59e0b" label="Protection" dashed />
      </span>
    </div>
  )
}

function LegendEdge({ color, label, dashed }: { color: string; label: string
  dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="20" height="4">
        <line x1="0" y1="2" x2="20" y2="2" stroke={color} strokeWidth="2"
          strokeDasharray={dashed ? '4 3' : undefined} />
      </svg>
      {label}
    </span>
  )
}

function NodeInspector({ node, status, trace, onSelect }: {
  node: CircuitNode
  status?: TerminalStatus
  trace: TracePayload | null
  onSelect: (key: string) => void
}) {
  const overlayTone = status?.overlay_color === 'GREEN' ? 'ok'
    : status?.overlay_color === 'RED' ? 'fault'
    : status?.overlay_color === 'YELLOW' ? 'warn' : 'unknown'

  return (
    <>
      <Panel title={node.label || node.key}>
        <dl className="grid grid-cols-[110px_1fr] gap-y-1.5 gap-x-3 text-xs">
          <Row label="Key" value={<span className="font-mono">{node.key}</span>} />
          <Row label="Type" value={node.node_type.replace(/_/g, ' ')} />
          {node.terminal && <Row label="Terminal" value={node.terminal.tag} />}
          {node.wire && <Row label="Wire" value={node.wire.wire_number} />}
          {node.component && (
            <>
              <Row label="Designator" value={node.component.reference_designator} />
              <Row label="Description" value={node.component.description || '—'} />
              <Row label="Rating" value={node.component.rating || '—'} />
              <Row label="Location" value={node.component.location || '—'} />
            </>
          )}
          {node.controller_signal && (
            <Row label="Controller I/O" value={node.controller_signal} />
          )}
          <Row label="Nominal" value={node.nominal_voltage_v
            ? `${node.nominal_voltage_v} V` : '—'} />
          <Row label="Verified" value={node.verified
            ? 'Yes'
            : <span className="text-amber-300">
                No — {Math.round(node.confidence * 100)}% confidence
              </span>} />
        </dl>
      </Panel>

      {node.medium_voltage && (
        <SafetyNotice>
          <strong className="block mb-1">MEDIUM VOLTAGE — {node.nominal_voltage_v} V</strong>
          {node.safety_notice}
        </SafetyNotice>
      )}

      <Panel title="Status">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <StatusDot tone={overlayTone} label={status?.status ?? 'UNKNOWN'} />
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">{status?.reason}</p>

          <Fact
            title="Expected"
            body={status?.expected
              ? `${status.expected.value} ${status.expected.unit} ±${status.expected.tolerance_pct}%
                 (${status.expected.min.toFixed(2)}–${status.expected.max.toFixed(2)} ${status.expected.unit})
                 with respect to ${status.expected.reference || 'circuit reference'}`
              : 'No engineering expectation configured for this point.'}
            source="EXPECTATION"
            basis={status?.expected?.basis}
          />

          <Fact
            title="Measured"
            body={status?.measured
              ? `${formatValue(status.measured.value, status.measured.unit)} · ${status.measured.method ?? 'measurement'}
                 ${status.measured.instrument ? `· ${status.measured.instrument}` : ''}`
              : 'NOT MEASURED — no physical measurement exists at this point.'}
            source={status?.measured?.source}
            quality={status?.measured?.quality}
            basis={status?.measured?.timestamp
              ? formatDateTime(status.measured.timestamp) : undefined}
          />

          <Fact
            title="Controller"
            body={status?.controller
              ? `${status.controller.signal} = ${
                  typeof status.controller.value === 'boolean'
                    ? (status.controller.value ? 'ON' : 'OFF')
                    : String(status.controller.value ?? '—')}`
              : 'No controller signal associated with this node.'}
            source={status?.controller?.source}
            quality={status?.controller?.quality}
            note={status?.controller?.note}
          />
        </div>
      </Panel>

      {trace && (
        <Panel title={`Trace ${trace.direction} from ${trace.start}`} dense>
          <div className="p-3 space-y-3 max-h-80 overflow-y-auto">
            {trace.paths.length === 0 && (
              <p className="text-xs text-slate-500">No path in this direction.</p>
            )}
            {trace.paths.slice(0, 6).map((path, index) => (
              <div key={index} className="space-y-1">
                {path.map((step, i) => (
                  <div key={`${step.key}-${i}`} className="flex items-center gap-2">
                    <span className="text-slate-700 text-xs w-4 text-center">
                      {i === 0 ? '' : '↓'}
                    </span>
                    <button
                      className="text-xs text-slate-200 hover:text-blue-300 font-mono"
                      onClick={() => onSelect(step.key)}
                    >
                      {step.key}
                    </button>
                    {step.via?.wire_number && (
                      <span className="text-[10px] text-slate-600">{step.via.wire_number}</span>
                    )}
                  </div>
                ))}
              </div>
            ))}
            {trace.truncated && (
              <p className="text-2xs text-amber-400">
                Trace truncated at the depth limit — some branches are not shown.
              </p>
            )}
          </div>
        </Panel>
      )}
    </>
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

function Fact({ title, body, source, quality, basis, note }: {
  title: string; body: string; source?: string; quality?: string
  basis?: string; note?: string
}) {
  return (
    <div className="rounded border border-edge bg-panel-900/60 px-3 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="label">{title}</span>
        {source && <SourceBadge source={source as never} quality={quality as never} />}
      </div>
      <p className="text-xs text-slate-300 leading-relaxed">{body}</p>
      {basis && <p className="text-[10px] text-slate-600 mt-1">{basis}</p>}
      {note && <p className="text-[10px] text-blue-400/80 mt-1 italic">{note}</p>}
    </div>
  )
}
