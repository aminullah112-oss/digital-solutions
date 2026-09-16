import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from './api'
import { wsUrl } from './config'
import type { ValueEnvelope } from './types'

/** Fetch with loading/error state and manual refresh. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(Boolean(path))

  const load = useCallback(async () => {
    if (!path) { setLoading(false); return }
    setLoading(true)
    try {
      setData(await api.get<T>(path))
      setError(null)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps])

  useEffect(() => { void load() }, [load])
  return { data, error, loading, reload: load, setData }
}

/** Poll an endpoint. Used for screens whose data has no WebSocket topic. */
export function usePolling<T>(path: string | null, intervalMs = 2000) {
  const { data, error, loading, reload, setData } = useApi<T>(path)
  useEffect(() => {
    if (!path) return
    const id = setInterval(() => { void reload() }, intervalMs)
    return () => clearInterval(id)
  }, [path, intervalMs, reload])
  return { data, error, loading, reload, setData }
}

/**
 * Live values for one controller over WebSocket, with polling as a fallback.
 *
 * The socket can drop without the browser noticing for a while, so the hook
 * tracks its own connection state and the screen shows it. A silent, frozen
 * dashboard is the failure mode to avoid.
 */
export function useLiveValues(controllerId: number | null) {
  const [values, setValues] = useState<Record<string, ValueEnvelope>>({})
  const [connected, setConnected] = useState(false)
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (controllerId === null) return
    setValues({})
    let closed = false
    let retry: ReturnType<typeof setTimeout>

    const connect = () => {
      if (closed) return
      const socket = new WebSocket(wsUrl(`/ws/controllers/${controllerId}`))
      socketRef.current = socket

      socket.onopen = () => setConnected(true)
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data)
        if (message.type === 'values') {
          setValues((prev) => ({ ...prev, ...message.values }))
          setLastMessageAt(Date.now())
        } else if (message.type === 'controller_status') {
          setValues({})
          setLastMessageAt(Date.now())
        }
      }
      socket.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 2000)
      }
      socket.onerror = () => socket.close()
    }

    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      socketRef.current?.close()
    }
  }, [controllerId])

  return { values, connected, lastMessageAt }
}

export function useKeyboard(handlers: Record<string, (event: KeyboardEvent) => void>) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      const typing = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA'
        || target.isContentEditable
      const combo = [
        event.ctrlKey || event.metaKey ? 'mod' : '',
        event.shiftKey ? 'shift' : '',
        event.key.toLowerCase(),
      ].filter(Boolean).join('+')

      const handler = handlers[combo]
      if (!handler) return
      // Bare letter shortcuts must not fire while someone is typing a tag.
      if (typing && !combo.startsWith('mod')) return
      event.preventDefault()
      handler(event)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [handlers])
}

/** Selected project, persisted so a reload does not lose context. */
export function useSelectedProject(): [number | null, (id: number | null) => void] {
  const [projectId, setProjectId] = useState<number | null>(() => {
    const stored = localStorage.getItem('powertrace.project')
    return stored ? Number(stored) : null
  })
  const set = useCallback((id: number | null) => {
    setProjectId(id)
    if (id === null) localStorage.removeItem('powertrace.project')
    else localStorage.setItem('powertrace.project', String(id))
    window.dispatchEvent(new CustomEvent('powertrace:project', { detail: id }))
  }, [])

  useEffect(() => {
    const onChange = (event: Event) => {
      setProjectId((event as CustomEvent<number | null>).detail)
    }
    window.addEventListener('powertrace:project', onChange)
    return () => window.removeEventListener('powertrace:project', onChange)
  }, [])

  return [projectId, set]
}
