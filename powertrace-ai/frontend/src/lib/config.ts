// Where the API lives.
//
// Two deployment shapes are supported and they need different answers:
//
//   Single origin  — nginx (or any reverse proxy) serves the built frontend and
//                    forwards /api and /ws to the backend. Nothing to set; the
//                    WebSocket then shares the page's origin, which is what you
//                    want because it inherits the TLS certificate and any auth
//                    at the edge.
//   Split hosts    — frontend on a static host, backend elsewhere. Set
//                    VITE_API_BASE at build time. The backend's
//                    POWERTRACE_CORS_ORIGINS must then name the frontend origin.
//
// Prefer single origin. Splitting hosts means CORS, a second certificate, and a
// WebSocket crossing origins — three more things to be wrong at 03:00.

const RAW_BASE = (import.meta.env.VITE_API_BASE ?? '').trim().replace(/\/+$/, '')

export const API_BASE = RAW_BASE

export function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path
}

export function wsUrl(path: string): string {
  if (!API_BASE) {
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    return `${protocol}://${location.host}${path}`
  }
  return API_BASE.replace(/^http/, 'ws') + path
}
