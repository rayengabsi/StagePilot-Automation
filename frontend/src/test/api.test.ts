import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api } from '../api/client'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

function mockJson(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  }
}

describe('api client', () => {
  it('health returns status', async () => {
    mockFetch.mockResolvedValue(mockJson({ status: 'ok' }))
    const res = await api.health()
    expect(res).toEqual({ status: 'ok' })
    expect(mockFetch).toHaveBeenCalledWith('/api/health', expect.objectContaining({
      headers: { 'Content-Type': 'application/json' },
    }))
  })

  it('jobs builds query string', async () => {
    mockFetch.mockResolvedValue(mockJson({ total: 2, limit: 10, offset: 0, items: [] }))
    await api.jobs({ limit: 10, offset: 5 })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('limit=10')
    expect(url).toContain('offset=5')
  })

  it('filters.update sends PUT', async () => {
    mockFetch.mockResolvedValue(mockJson({ excluded_keywords: ['foo'] }))
    await api.filters.update({ excluded_keywords: ['foo'] })
    expect(mockFetch).toHaveBeenCalledWith('/api/filters', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify({ excluded_keywords: ['foo'] }),
    }))
  })

  it('scheduler.once sends POST', async () => {
    mockFetch.mockResolvedValue(mockJson({ status: 'ok' }))
    await api.scheduler.once()
    expect(mockFetch).toHaveBeenCalledWith('/api/scheduler/once', expect.objectContaining({ method: 'POST' }))
  })
})
