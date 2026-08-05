import { vi } from 'vitest'

export type Handler = { status?: number; body: unknown }

/**
 * Stub `fetch` with a per-route response map.
 *
 * Keys are `"<METHOD> <path>"`, e.g. `"DELETE /api/me/tokens/t1"`; the query
 * string is ignored. A bare value is returned as a 200 body, and
 * `{ status, body }` drives an error path.
 *
 * Shared so page tests do not each grow their own copy.
 */
export function mockApi(
  handlers: Record<string, Handler | unknown> = {},
  fallback: unknown = {},
) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(url).split('?')[0]}`
    const entry = key in handlers ? handlers[key] : fallback
    const { status = 200, body } =
      entry && typeof entry === 'object' && 'body' in entry
        ? (entry as Handler)
        : { status: 200, body: entry }
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
