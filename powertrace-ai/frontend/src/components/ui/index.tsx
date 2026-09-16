import { type ReactNode } from 'react'
import { AlertTriangle, Info } from 'lucide-react'
import type { DataSource, Quality } from '@/lib/types'
import { formatAge, qualityClass, sourceClass, sourceLabel } from '@/lib/format'

export function Panel({ title, actions, children, className = '', dense = false }: {
  title?: ReactNode; actions?: ReactNode; children: ReactNode
  className?: string; dense?: boolean
}) {
  return (
    <section className={`panel ${className}`}>
      {(title || actions) && (
        <header className="panel-header">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-300">{title}</h2>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={dense ? '' : 'p-4'}>{children}</div>
    </section>
  )
}

/**
 * Status indicator. Colour is never the only channel — every dot ships with
 * a label, because a red/green-only interface fails for roughly 1 in 12 men
 * and is unreadable on a sunlit tablet in a switchgear room.
 */
export function StatusDot({ tone, label, title }: {
  tone: 'ok' | 'fault' | 'warn' | 'info' | 'unknown'
  label: string
  title?: string
}) {
  const colors = {
    ok: 'bg-ok shadow-[0_0_6px_rgba(34,197,94,0.6)]',
    fault: 'bg-fault shadow-[0_0_6px_rgba(239,68,68,0.6)]',
    warn: 'bg-warn shadow-[0_0_6px_rgba(245,158,11,0.6)]',
    info: 'bg-info shadow-[0_0_6px_rgba(59,130,246,0.6)]',
    unknown: 'bg-unknown',
  }
  const text = {
    ok: 'text-emerald-300', fault: 'text-red-300', warn: 'text-amber-300',
    info: 'text-blue-300', unknown: 'text-slate-400',
  }
  return (
    <span className="inline-flex items-center gap-1.5" title={title ?? label}>
      <span className={`h-2 w-2 rounded-full shrink-0 ${colors[tone]}`} />
      <span className={`text-2xs font-semibold uppercase tracking-wide ${text[tone]}`}>{label}</span>
    </span>
  )
}

export function SourceBadge({ source, quality, age }: {
  source?: DataSource; quality?: Quality; age?: number | null
}) {
  // The quality badge only earns its space when it says something the source
  // badge does not — "SIMULATED SIMULATED" is noise on every row.
  const showQuality = quality && quality !== 'GOOD' && quality !== sourceLabel(source)
  return (
    <span className="inline-flex items-center gap-1 shrink-0">
      <span className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold tracking-wide
        whitespace-nowrap ${sourceClass(source)}`}>
        {sourceLabel(source)}
      </span>
      {showQuality && (
        <span className="px-1.5 py-0.5 rounded border border-slate-600/40 bg-slate-700/30
          text-[10px] font-semibold text-slate-300">{quality}</span>
      )}
      {age !== undefined && age !== null && age > 2 && (
        <span className="text-[10px] text-slate-500">{formatAge(age)}</span>
      )}
    </span>
  )
}

export function Metric({ label, value, unit, quality, source, sub, tone }: {
  label: string; value: ReactNode; unit?: string; quality?: Quality
  source?: DataSource; sub?: ReactNode; tone?: 'ok' | 'fault' | 'warn' | 'default'
}) {
  const toneClass = tone === 'fault' ? 'text-red-300'
    : tone === 'warn' ? 'text-amber-300'
    : tone === 'ok' ? 'text-emerald-300'
    : qualityClass(quality)
  return (
    <div className="panel px-3.5 py-3">
      <div className="label mb-1.5">{label}</div>
      <div className={`text-2xl value leading-none ${toneClass}`}>
        {value}
        {unit && <span className="text-sm font-medium text-slate-500 ml-1">{unit}</span>}
      </div>
      <div className="mt-2 flex items-center gap-2 min-h-[18px]">
        {source && <SourceBadge source={source} quality={quality} />}
        {sub && <span className="text-2xs text-slate-500">{sub}</span>}
      </div>
    </div>
  )
}

export function SafetyNotice({ children, tone = 'warn' }: {
  children: ReactNode; tone?: 'warn' | 'info'
}) {
  const styles = tone === 'warn'
    ? 'border-amber-600/50 bg-amber-950/30 text-amber-200'
    : 'border-blue-600/40 bg-blue-950/20 text-blue-200'
  const Icon = tone === 'warn' ? AlertTriangle : Info
  return (
    <div className={`flex items-start gap-2 rounded border px-3 py-2 text-xs ${styles}`}>
      <Icon className="h-4 w-4 shrink-0 mt-0.5" />
      <div className="leading-relaxed">{children}</div>
    </div>
  )
}

export function Empty({ title, hint, icon: Icon }: {
  title: string; hint?: string; icon?: React.ComponentType<{ className?: string }>
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {Icon && <Icon className="h-8 w-8 text-slate-700 mb-3" />}
      <p className="text-sm text-slate-400">{title}</p>
      {hint && <p className="text-xs text-slate-600 mt-1.5 max-w-md">{hint}</p>}
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500 py-8 justify-center">
      <span className="h-3 w-3 rounded-full border-2 border-slate-600 border-t-blue-400
        animate-spin" />
      {label ?? 'Loading…'}
    </div>
  )
}

export function ErrorNote({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="flex items-start gap-2 rounded border border-red-700/50 bg-red-950/30
      px-3 py-2 text-xs text-red-200">
      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
      <div className="flex-1">{error}</div>
      {onRetry && <button className="btn py-0.5" onClick={onRetry}>Retry</button>}
    </div>
  )
}

export function Confidence({ level }: { level: string }) {
  const map: Record<string, string> = {
    CONFIRMED_BY_MEASUREMENT: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
    LIKELY: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
    POSSIBLE: 'bg-slate-500/15 text-slate-300 border-slate-500/40',
    UNVERIFIED: 'bg-slate-700/40 text-slate-400 border-slate-600/40',
  }
  const text: Record<string, string> = {
    CONFIRMED_BY_MEASUREMENT: 'CONFIRMED BY MEASUREMENT',
    LIKELY: 'LIKELY', POSSIBLE: 'POSSIBLE', UNVERIFIED: 'UNVERIFIED',
  }
  return (
    <span className={`px-2 py-0.5 rounded border text-[10px] font-bold tracking-wide
      ${map[level] ?? map.UNVERIFIED}`}>
      {text[level] ?? level}
    </span>
  )
}
