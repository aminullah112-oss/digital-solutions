import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { getToken } from '@/lib/api'
import { Shell } from '@/components/layout/Shell'
import { Login } from '@/pages/Login'
import { Dashboard } from '@/pages/Dashboard'
import { Controllers } from '@/pages/Controllers'
import { LiveData } from '@/pages/LiveData'
import { Schematics } from '@/pages/Schematics'
import { CircuitExplorer } from '@/pages/CircuitExplorer'
import { Diagnostics } from '@/pages/Diagnostics'
import { Troubleshooting } from '@/pages/Troubleshooting'
import { Measurements } from '@/pages/Measurements'
import { Alarms } from '@/pages/Alarms'
import { Trends } from '@/pages/Trends'
import { Projects } from '@/pages/Projects'
import { Reports } from '@/pages/Reports'
import { SettingsPage } from '@/pages/Settings'

export function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()))

  useEffect(() => {
    const onUnauthorized = () => setAuthed(false)
    window.addEventListener('powertrace:unauthorized', onUnauthorized)
    return () => window.removeEventListener('powertrace:unauthorized', onUnauthorized)
  }, [])

  if (!authed) return <Login onSignedIn={() => setAuthed(true)} />

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/controllers" element={<Controllers />} />
        <Route path="/controllers/:controllerId" element={<Controllers />} />
        <Route path="/live" element={<LiveData />} />
        <Route path="/schematics" element={<Schematics />} />
        <Route path="/schematics/:schematicId" element={<Schematics />} />
        <Route path="/circuit" element={<CircuitExplorer />} />
        <Route path="/diagnostics" element={<Diagnostics />} />
        <Route path="/diagnostics/:sessionId" element={<Troubleshooting />} />
        <Route path="/troubleshooting" element={<Troubleshooting />} />
        <Route path="/measurements" element={<Measurements />} />
        <Route path="/alarms" element={<Alarms />} />
        <Route path="/trends" element={<Trends />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:projectId" element={<Projects />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  )
}
