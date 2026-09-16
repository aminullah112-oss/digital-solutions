import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api } from '@/lib/api'
import { useSelectedProject } from '@/lib/hooks'

interface Result {
  type: string
  id: number
  project_id: number
  title: string
  subtitle: string
  status?: string
  route: string
}

const TYPE_LABEL: Record<string, string> = {
  project: 'Project', controller: 'Controller', component: 'Component',
  terminal: 'Terminal', wire: 'Wire', circuit_node: 'Circuit node',
  schematic: 'Schematic', alarm: 'Alarm', diagnostic_session: 'Session',
}

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [active, setActive] = useState(0)
  const [projectId] = useSelectedProject()
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (open) {
      setQuery('')
      setResults([])
      setActive(0)
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [open])

  useEffect(() => {
    if (!open || query.trim().length < 1) { setResults([]); return }
    // Debounced: a search per keystroke against a plant database is wasteful.
    const id = setTimeout(async () => {
      try {
        const scope = projectId ? `&project_id=${projectId}` : ''
        const body = await api.get<{ results: Result[] }>(
          `/api/search?q=${encodeURIComponent(query)}${scope}`)
        setResults(body.results)
        setActive(0)
      } catch { setResults([]) }
    }, 160)
    return () => clearTimeout(id)
  }, [query, open, projectId])

  const grouped = useMemo(() => {
    const map = new Map<string, Result[]>()
    for (const result of results) {
      const list = map.get(result.type) ?? []
      list.push(result)
      map.set(result.type, list)
    }
    return [...map.entries()]
  }, [results])

  if (!open) return null

  const go = (result: Result) => {
    navigate(result.route)
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-start
        justify-center pt-28"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl panel shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-edge">
          <Search className="h-4 w-4 text-slate-500" />
          <input
            ref={inputRef}
            className="flex-1 bg-transparent outline-none text-sm text-slate-100
              placeholder:text-slate-600"
            placeholder="Search components, terminals, wires, controllers, alarms…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') onClose()
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setActive((i) => Math.min(i + 1, results.length - 1))
              }
              if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((i) => Math.max(i - 1, 0))
              }
              if (e.key === 'Enter' && results[active]) go(results[active])
            }}
          />
          <kbd className="px-1.5 py-0.5 rounded bg-panel-900 border border-edge text-[10px]
            text-slate-500">ESC</kbd>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {results.length === 0 ? (
            <p className="px-4 py-6 text-xs text-slate-600 text-center">
              {query ? 'No matches.' : 'Type a tag: K12, TB23-14, W-105, DO-07…'}
            </p>
          ) : (
            grouped.map(([type, items]) => (
              <div key={type}>
                <div className="px-4 pt-3 pb-1 label">{TYPE_LABEL[type] ?? type}</div>
                {items.map((result) => {
                  const index = results.indexOf(result)
                  return (
                    <button
                      key={`${type}-${result.id}`}
                      className={`w-full text-left px-4 py-2 flex items-center gap-3
                        ${index === active ? 'bg-panel-700' : 'hover:bg-panel-700/50'}`}
                      onMouseEnter={() => setActive(index)}
                      onClick={() => go(result)}
                    >
                      <span className="text-sm font-medium text-slate-100">{result.title}</span>
                      <span className="text-xs text-slate-500 truncate">{result.subtitle}</span>
                      {result.status && (
                        <span className="ml-auto text-[10px] text-slate-500">{result.status}</span>
                      )}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
