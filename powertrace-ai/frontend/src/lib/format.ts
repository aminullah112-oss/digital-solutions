import type { DataSource, Quality, ValueEnvelope } from './types'

// Formatting rules that hold everywhere in the UI.
//
// A null value renders as an em dash, never as 0. A stale value renders with
// its age. Nothing is rounded to fewer digits than the instrument supports.

export function formatValue(value: unknown, unit?: string, digits?: number): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'ON' : 'OFF'
  if (typeof value === 'number') {
    const decimals = digits ?? defaultDigits(unit)
    const text = Math.abs(value) >= 1000
      ? value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
      : value.toFixed(decimals)
    return unit ? `${text} ${unit}` : text
  }
  return String(value)
}

function defaultDigits(unit?: string): number {
  switch (unit) {
    case 'V': case 'A': return 1
    case 'Hz': return 2
    case 'kW': case 'kVAr': case 'kVA': return 0
    case '%': case 'psi': case 'degC': return 1
    case 'rpm': return 0
    case 'h': return 1
    default: return 2
  }
}

export function formatAge(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return ''
  if (seconds < 1) return 'now'
  if (seconds < 60) return `${seconds.toFixed(0)}s ago`
  if (seconds < 3600) return `${(seconds / 60).toFixed(0)}m ago`
  return `${(seconds / 3600).toFixed(1)}h ago`
}

export function formatTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString([], { hour12: false })
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString([], { hour12: false })
}

// Quality drives how a number is presented, not just a badge beside it.
export function qualityClass(quality?: Quality): string {
  switch (quality) {
    case 'GOOD': return 'text-slate-100'
    case 'SIMULATED': return 'text-amber-200'
    case 'STALE': return 'text-slate-400 italic'
    case 'BAD': case 'TIMEOUT': return 'text-red-300'
    default: return 'text-slate-500'
  }
}

export function sourceLabel(source?: DataSource): string {
  switch (source) {
    case 'MEASURED': return 'MEASURED'
    case 'CONTROLLER': return 'CONTROLLER'
    case 'SCHEMATIC': return 'SCHEMATIC'
    case 'EXPECTATION': return 'EXPECTED'
    case 'INFERENCE': return 'INFERRED'
    case 'SIMULATED': return 'SIMULATED'
    default: return 'UNKNOWN'
  }
}

export function sourceClass(source?: DataSource): string {
  switch (source) {
    case 'MEASURED': return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    case 'CONTROLLER': return 'bg-blue-500/15 text-blue-300 border-blue-500/30'
    case 'SCHEMATIC': return 'bg-violet-500/15 text-violet-300 border-violet-500/30'
    case 'EXPECTATION': return 'bg-slate-500/15 text-slate-300 border-slate-500/30'
    case 'INFERENCE': return 'bg-amber-500/15 text-amber-300 border-amber-500/30'
    case 'SIMULATED': return 'bg-orange-500/15 text-orange-300 border-orange-500/30'
    default: return 'bg-slate-700/40 text-slate-400 border-slate-600/40'
  }
}

export function isLive(envelope?: ValueEnvelope | null): boolean {
  if (!envelope) return false
  return envelope.quality === 'GOOD' || envelope.quality === 'SIMULATED'
}
