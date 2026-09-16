import { useState } from 'react'
import { Zap } from 'lucide-react'
import { login } from '@/lib/api'
import { ErrorNote, SafetyNotice } from '@/components/ui'

export function Login({ onSignedIn }: { onSignedIn: () => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      onSignedIn()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-panel-900 p-6">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4">
        <div className="flex items-center gap-2.5 mb-6">
          <Zap className="h-7 w-7 text-blue-400" />
          <div>
            <h1 className="text-lg font-bold text-slate-100">PowerTrace AI</h1>
            <p className="text-xs text-slate-500">
              Industrial electrical troubleshooting
            </p>
          </div>
        </div>

        <div className="panel p-5 space-y-3">
          <div>
            <label className="label block mb-1">Email</label>
            <input className="input" value={email} autoComplete="username"
              onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div>
            <label className="label block mb-1">Password</label>
            <input className="input" type="password" value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <ErrorNote error={error} />}
          <button className="btn btn-primary w-full justify-center" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </div>

        <SafetyNotice>
          This application is a diagnostic aid. It is not a safety-rated protection system
          and issues no control commands. Nothing it displays establishes that a circuit is
          de-energized.
        </SafetyNotice>
      </form>
    </div>
  )
}
