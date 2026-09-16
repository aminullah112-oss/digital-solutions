// Thin API client. Errors surface the server's message rather than a generic
// "request failed" — during troubleshooting, the reason matters.

const TOKEN_KEY = 'powertrace.token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) {
    super(message)
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(path, { ...init, headers })
  if (response.status === 401) {
    setToken(null)
    window.dispatchEvent(new CustomEvent('powertrace:unauthorized'))
  }
  const text = await response.text()
  const body = text ? tryParse(text) : null

  if (!response.ok) {
    const detail = (body as any)?.detail
    const message =
      typeof detail === 'string' ? detail
      : detail?.message ? detail.message
      : Array.isArray(detail) ? detail.map((d: any) => d.msg ?? String(d)).join('; ')
      : `${response.status} ${response.statusText}`
    throw new ApiError(response.status, message, detail)
  }
  return body as T
}

function tryParse(text: string): unknown {
  try { return JSON.parse(text) } catch { return text }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: 'POST', body: form }),
  raw: (path: string) => {
    const token = getToken()
    return fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  },
}

export async function login(email: string, password: string) {
  const result = await api.post<{ access_token: string; role: string; email: string
    permissions: string[] }>('/api/auth/token', { email, password })
  setToken(result.access_token)
  return result
}
