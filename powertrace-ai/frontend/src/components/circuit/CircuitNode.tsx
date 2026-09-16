import { Handle, Position, type NodeProps } from '@xyflow/react'
import {
  AlertTriangle, Battery, CircuitBoard, Cpu, Gauge, HelpCircle, Minus, Plug, Power,
  Shield, Square, ToggleLeft, Zap,
} from 'lucide-react'
import type { TerminalStatus } from '@/lib/types'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  SOURCE: Battery, FUSE: Shield, BREAKER: Power, CONTACTOR: Square, RELAY: CircuitBoard,
  RELAY_COIL: CircuitBoard, RELAY_CONTACT: ToggleLeft, TERMINAL: Plug, CONNECTOR: Plug,
  WIRE: Minus, SWITCH: ToggleLeft, SENSOR: Gauge, TRANSDUCER: Gauge,
  CONTROLLER_INPUT: Cpu, CONTROLLER_OUTPUT: Cpu, LOAD: Zap, GROUND: Minus,
  BUS: Minus, TRANSFORMER: Zap, PT: Zap, CT: Zap, UNKNOWN: HelpCircle,
}

/**
 * Overlay colour comes from the measurement comparison alone. A node with no
 * measurement is gray and says NOT MEASURED, whatever the controller reports
 * about it.
 */
const OVERLAY: Record<string, { ring: string; text: string; bg: string }> = {
  GREEN: { ring: 'border-emerald-500/70', text: 'text-emerald-300', bg: 'bg-emerald-950/30' },
  RED: { ring: 'border-red-500/80', text: 'text-red-300', bg: 'bg-red-950/40' },
  YELLOW: { ring: 'border-amber-500/70', text: 'text-amber-300', bg: 'bg-amber-950/30' },
  BLUE: { ring: 'border-blue-500/70', text: 'text-blue-300', bg: 'bg-blue-950/30' },
  GRAY: { ring: 'border-edge', text: 'text-slate-500', bg: 'bg-panel-800' },
}

export interface CircuitNodeData extends Record<string, unknown> {
  label: string
  nodeType: string
  status?: TerminalStatus
  controllerSignal?: string
  mediumVoltage?: boolean
  verified: boolean
  confidence: number
  highlighted?: boolean
  suspect?: boolean
}

export function CircuitNodeCard({ data, selected }: NodeProps) {
  const d = data as CircuitNodeData
  const Icon = ICONS[d.nodeType] ?? HelpCircle
  const overlay = OVERLAY[d.status?.overlay_color ?? 'GRAY'] ?? OVERLAY.GRAY
  const measured = d.status?.measured
  const controller = d.status?.controller

  return (
    <div
      className={`w-[196px] rounded border-2 px-2.5 py-2 transition-all
        ${overlay.ring} ${overlay.bg}
        ${selected ? 'ring-2 ring-blue-400 ring-offset-2 ring-offset-panel-900' : ''}
        ${d.highlighted ? 'shadow-[0_0_0_2px_rgba(59,130,246,0.45)]' : ''}
        ${d.suspect ? 'shadow-[0_0_14px_rgba(239,68,68,0.5)]' : ''}
        ${d.highlighted === false ? 'opacity-30' : ''}`}
    >
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />

      <div className="flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 shrink-0 ${overlay.text}`} />
        <span className="text-[11px] font-semibold text-slate-100 truncate">{d.label}</span>
        {d.mediumVoltage && (
          <AlertTriangle className="h-3 w-3 text-amber-400 shrink-0" />
        )}
      </div>

      <div className="text-[9px] uppercase tracking-wide text-slate-600 mt-0.5">
        {d.nodeType.replace(/_/g, ' ')}
      </div>

      {/* Measured, expected and controller state occupy separate lines. They
          are different facts and are never merged into one number. */}
      <div className="mt-1.5 space-y-0.5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[9px] text-slate-600">MEAS</span>
          <span className={`text-[11px] font-semibold tnum ${overlay.text}`}>
            {measured?.value !== undefined && measured?.value !== null
              ? `${measured.value} ${measured.unit}`
              : 'NOT MEASURED'}
          </span>
        </div>
        {d.status?.expected?.value !== undefined && d.status?.expected !== null && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[9px] text-slate-600">EXP</span>
            <span className="text-[10px] text-slate-400 tnum">
              {d.status.expected.value} {d.status.expected.unit}
            </span>
          </div>
        )}
        {controller && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[9px] text-blue-500">CTRL</span>
            <span className="text-[10px] text-blue-300 tnum">
              {controller.value === null || controller.value === undefined
                ? '—'
                : typeof controller.value === 'boolean'
                  ? (controller.value ? 'ON' : 'OFF')
                  : String(controller.value)}
            </span>
          </div>
        )}
      </div>

      {!d.verified && (
        <div className="mt-1 text-[9px] text-amber-400">
          UNVERIFIED {Math.round(d.confidence * 100)}%
        </div>
      )}
    </div>
  )
}
