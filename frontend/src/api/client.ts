const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API ${res.status}: ${body}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/health'),
  profile: () => request<Record<string, unknown>>('/profile'),
  filters: {
    get: () => request<Record<string, unknown>>('/filters'),
    update: (rules: Record<string, unknown>) =>
      request<Record<string, unknown>>('/filters', {
        method: 'PUT',
        body: JSON.stringify(rules),
      }),
  },
  scheduler: {
    status: () => request<Record<string, unknown>>('/scheduler/status'),
    once: () =>
      request<{ status: string }>('/scheduler/once', { method: 'POST' }),
    start: (interval_minutes?: number) =>
      request<{ status: string }>('/scheduler/start', {
        method: 'POST',
        body: JSON.stringify({ interval_minutes }),
      }),
    stop: () =>
      request<{ status: string }>('/scheduler/stop', { method: 'POST' }),
  },
  jobs: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    const qs = q.toString()
    return request<{ total: number; limit: number; offset: number; items: Record<string, unknown>[] }>(
      `/jobs${qs ? `?${qs}` : ''}`,
    )
  },
  matches: (params?: { limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    const qs = q.toString()
    return request<{ total: number; limit: number; offset: number; items: Record<string, unknown>[] }>(
      `/matches${qs ? `?${qs}` : ''}`,
    )
  },
}
