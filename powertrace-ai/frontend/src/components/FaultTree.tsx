import { useState } from 'react'
import { ChevronDown, ChevronRight, CircleDot, HelpCircle, MinusCircle, XCircle } from 'lucide-react'
import type { FaultTreeNode } from '@/lib/types'

const STATUS = {
  SUSPECT: { icon: CircleDot, color: 'text-red-400', label: 'SUSPECT' },
  RULED_OUT: { icon: MinusCircle, color: 'text-emerald-400', label: 'RULED OUT' },
  NOT_MEASURED: { icon: HelpCircle, color: 'text-slate-500', label: 'NOT MEASURED' },
  UNVERIFIED: { icon: XCircle, color: 'text-amber-400', label: 'UNVERIFIED' },
} as const

export function FaultTree({ node, depth = 0 }: { node: FaultTreeNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 2)
  const meta = STATUS[node.status] ?? STATUS.UNVERIFIED
  const Icon = meta.icon
  const hasChildren = node.children.length > 0

  return (
    <div className={depth > 0 ? 'ml-4 border-l border-edge pl-3' : ''}>
      <div className="flex items-start gap-2 py-1.5">
        {hasChildren ? (
          <button onClick={() => setOpen(!open)} className="mt-0.5 text-slate-600
            hover:text-slate-300">
            {open ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        ) : (
          <span className="w-3.5" />
        )}
        <Icon className={`h-3.5 w-3.5 mt-0.5 shrink-0 ${meta.color}`} />
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-200">{node.label}</span>
            <span className={`text-[9px] font-bold tracking-wide ${meta.color}`}>
              {meta.label}
            </span>
          </div>
          {node.detail && (
            <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">{node.detail}</p>
          )}
        </div>
      </div>
      {open && hasChildren && node.children.map((child) => (
        <FaultTree key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}
