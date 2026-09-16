import { type ReactNode, useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity, AlertTriangle, Binary, Cable, Cpu, FileText, FolderKanban, Gauge,
  LayoutDashboard, LineChart, Search, Settings, Stethoscope, Wrench, Zap,
} from 'lucide-react'
import { api, setToken } from '@/lib/api'
import { useKeyboard, useSelectedProject } from '@/lib/hooks'
import type { Project, SystemStatus } from '@/lib/types'
import { formatDateTime } from '@/lib/format'
import { StatusDot } from '@/components/ui'
import { CommandPalette } from './CommandPalette'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/controllers', label: 'Controllers', icon: Cpu },
  { to: '/live', label: 'Live Data', icon: Gauge },
  { to: '/schematics', label: 'Schematics', icon: Binary },
  { to: '/circuit', label: 'Circuit Explorer', icon: Cable },
  { to: '/diagnostics', label: 'Diagnostics', icon: Stethoscope },
  { to: '/troubleshooting', label: 'Troubleshooting', icon: Wrench },
  { to: '/measurements', label: 'Measurements', icon: Activity },
  { to: '/alarms', label: 'Alarms & Events', icon: AlertTriangle },
  { to: '/trends', label: 'Trends', icon: LineChart },
  { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Shell({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useSelectedProject()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const load = async () => {
      try {
        setStatus(await api.get<SystemStatus>('/api/system/status'))
      } catch { /* the banner shows the disconnected state */ }
    }
    void load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    api.get<Project[]>('/api/projects').then((list) => {
      setProjects(list)
      if (projectId === null && list.length) setProjectId(list[0].id)
    }).catch(() => undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useKeyboard({
    'mod+k': () => setPaletteOpen(true),
    'd': () => navigate('/diagnostics'),
  })

  const project = projects.find((p) => p.id === projectId)
  const offline = status === null

  return (
    <div className="min-h-screen flex bg-panel-900">
      <aside className="w-56 shrink-0 border-r border-edge bg-panel-850 flex flex-col">
        <div className="h-14 px-4 flex items-center gap-2 border-b border-edge">
          <Zap className="h-5 w-5 text-blue-400" />
          <div>
            <div className="text-sm font-bold tracking-tight text-slate-100">PowerTrace AI</div>
            <div className="text-[10px] text-slate-500 -mt-0.5">Electrical diagnostics</div>
          </div>
        </div>

        <nav className="flex-1 py-2 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `flex items-center gap-2.5 px-4 py-2 text-xs
                font-medium transition-colors border-l-2 ${isActive
                  ? 'border-blue-500 bg-panel-800 text-slate-100'
                  : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-panel-800/60'}`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-edge p-3 space-y-2">
          <div className="label">Active project</div>
          <select
            className="input py-1 text-xs"
            value={projectId ?? ''}
            onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">No project selected</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {project?.is_demo && (
            <div className="text-[10px] text-orange-300 font-semibold">DEMO PROJECT</div>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 border-b border-edge bg-panel-850 px-5
          flex items-center gap-4">
          <Breadcrumbs path={location.pathname} project={project?.name} />
          <div className="flex-1" />

          <button
            className="btn text-slate-400"
            onClick={() => setPaletteOpen(true)}
            title="Global search"
          >
            <Search className="h-3.5 w-3.5" />
            Search
            <kbd className="ml-1 px-1 py-0.5 rounded bg-panel-900 border border-edge
              text-[10px] text-slate-500">Ctrl K</kbd>
          </button>

          <div className="flex items-center gap-3 pl-3 border-l border-edge">
            {offline ? (
              <StatusDot tone="fault" label="Server unreachable" />
            ) : (
              <>
                <StatusDot
                  tone={status.controllers.online > 0 ? 'ok'
                    : status.controllers.total === 0 ? 'unknown' : 'fault'}
                  label={`${status.controllers.online}/${status.controllers.total} online`}
                />
                {status.alarms.active > 0 && (
                  <StatusDot tone="fault" label={`${status.alarms.active} active`} />
                )}
                <span className="text-[10px] text-slate-500">
                  Sync {formatDateTime(status.last_synchronization)}
                </span>
              </>
            )}
            <button
              className="btn py-1"
              onClick={() => { setToken(null); window.location.reload() }}
            >
              Sign out
            </button>
          </div>
        </header>

        {status?.demo_mode && (
          <div className="bg-orange-900/40 border-b border-orange-700/50 px-5 py-1.5
            flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 text-orange-300" />
            <span className="text-[11px] font-bold tracking-wide text-orange-200">
              DEMO MODE — SIMULATED DATA. Values tagged SIMULATED are not measurements of
              any real equipment.
            </span>
          </div>
        )}

        <main className="flex-1 overflow-auto p-5">{children}</main>

        <footer className="shrink-0 border-t border-edge bg-panel-850 px-5 py-1.5
          flex items-center gap-4 text-[10px] text-slate-500">
          <span className="font-semibold text-slate-400">
            NOT A SAFETY-RATED SYSTEM — ISSUES NO CONTROL COMMANDS
          </span>
          <span>
            VERIFY WITH APPROPRIATELY RATED TEST EQUIPMENT AND FOLLOW SITE SAFETY PROCEDURES.
          </span>
        </footer>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}

function Breadcrumbs({ path, project }: { path: string; project?: string }) {
  const current = NAV.find((n) => n.to !== '/' && path.startsWith(n.to))
    ?? NAV.find((n) => n.to === '/')
  return (
    <div className="flex items-center gap-2 text-xs">
      {project && <span className="text-slate-500">{project}</span>}
      {project && <span className="text-slate-700">/</span>}
      <span className="text-slate-200 font-medium">{current?.label}</span>
    </div>
  )
}
