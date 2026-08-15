import { describe, expect, it, vi } from 'vitest'
import { apiErrorMessage, apiFetch, readApiResponse } from './api'

/**
 * QA-FE-01. This module is the reason an API failure surfaces to the user
 * instead of becoming an empty list. Phase 2 hardened it; nothing pinned that
 * behaviour, so a regression here would silently reintroduce the exact defect
 * the roadmap calls out ("Avoid silently translating API failures into empty
 * lists").
 */

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
}

describe('readApiResponse', () => {
  it('returns the parsed payload on success', async () => {
    const data = await readApiResponse(jsonResponse({ ok: true, items: [1, 2] }))
    expect(data).toEqual({ ok: true, items: [1, 2] })
  })

  it('throws on a non-2xx response instead of returning empty data', async () => {
    await expect(
      readApiResponse(jsonResponse({ error: { message: 'Forbidden' } }, { status: 403 })),
    ).rejects.toMatchObject({ message: 'Forbidden' })
  })

  it('throws when the body says ok:false even though HTTP is 200', async () => {
    // The backend returns application-level failures this way. Treating a
    // 200 as success regardless of the body is how empty-list bugs appear.
    await expect(
      readApiResponse(jsonResponse({ ok: false, error: { message: 'Import rejected' } })),
    ).rejects.toMatchObject({ message: 'Import rejected' })
  })

  it('preserves the structured error code and details', async () => {
    const body = {
      error: { code: 'permission_denied', message: 'Not allowed', details: ['parts.read'] },
    }
    await expect(readApiResponse(jsonResponse(body, { status: 403 }))).rejects.toMatchObject({
      code: 'permission_denied',
      message: 'Not allowed',
      details: ['parts.read'],
    })
  })

  it('handles a string error payload', async () => {
    await expect(
      readApiResponse(jsonResponse({ error: 'rate_limited' }, { status: 429 })),
    ).rejects.toMatchObject({ code: 'rate_limited', message: 'rate_limited' })
  })

  it('falls back to a status message when the error carries no message', async () => {
    await expect(
      readApiResponse(jsonResponse({ error: {} }, { status: 500 })),
    ).rejects.toMatchObject({ message: 'Request failed (500)' })
  })

  it('reports a status message when an error response is not JSON', async () => {
    // A proxy or gateway returning HTML must not surface as a JSON parse error.
    const res = new Response('<html>502 Bad Gateway</html>', { status: 502 })
    await expect(readApiResponse(res)).rejects.toMatchObject({
      message: 'Request failed (502)',
    })
  })

  it('reports invalid JSON when the response was otherwise successful', async () => {
    const res = new Response('not json', { status: 200 })
    await expect(readApiResponse(res)).rejects.toMatchObject({
      message: expect.stringContaining('Invalid JSON response'),
    })
  })

  it('treats an empty body as a successful null payload', async () => {
    // Endpoints that return no content must not be reported as a parse error.
    // Status 200 rather than 204 because the Response constructor forbids a
    // body on 204, and the branch under test is "empty text", not the code.
    const res = new Response('', { status: 200 })
    await expect(readApiResponse(res)).resolves.toBeNull()
  })

  it('normalises non-array details to an empty array', async () => {
    await expect(
      readApiResponse(jsonResponse({ error: { message: 'x', details: 'oops' } }, { status: 400 })),
    ).rejects.toMatchObject({ details: [] })
  })
})

describe('apiErrorMessage', () => {
  it('uses the error message when present', () => {
    expect(apiErrorMessage({ message: 'Token expired' }, 'fallback')).toBe('Token expired')
  })

  it('falls back when the message is blank or whitespace', () => {
    expect(apiErrorMessage({ message: '   ' }, 'fallback')).toBe('fallback')
  })

  it('falls back for null, undefined and non-objects', () => {
    expect(apiErrorMessage(null, 'fallback')).toBe('fallback')
    expect(apiErrorMessage(undefined, 'fallback')).toBe('fallback')
    expect(apiErrorMessage('a string', 'fallback')).toBe('fallback')
  })
})

describe('apiFetch', () => {
  function stubFetch(response = jsonResponse({ ok: true })) {
    const mock = vi.fn().mockResolvedValue(response)
    vi.stubGlobal('fetch', mock)
    return mock
  }

  it('sends same-origin credentials so session auth works', async () => {
    // Strict mode authenticates the browser UI by session cookie; dropping
    // credentials would break every authenticated call.
    const fetchMock = stubFetch()
    await apiFetch('/api/parts')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/parts',
      expect.objectContaining({ credentials: 'same-origin' }),
    )
  })

  it('identifies the visible UI page for server-side audit records', async () => {
    const fetchMock = stubFetch()
    window.history.replaceState({}, '', '/ui/part/PART-100?rev=A')

    await apiFetch('/api/part_detail?pn=PART-100&rev=A')

    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers).toMatchObject({
      'X-TinyMRP-Page': '/ui/part/PART-100?rev=A',
    })
  })

  it('sets a JSON content type that callers can extend, e.g. a CSRF token', async () => {
    const fetchMock = stubFetch()
    await apiFetch('/api/parts', { method: 'POST', headers: { 'X-CSRFToken': 'abc123' } })
    const [, init] = fetchMock.mock.calls[0]
    expect(init).toMatchObject({
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': 'abc123' },
    })
  })

  it('propagates API errors to the caller rather than swallowing them', async () => {
    stubFetch(jsonResponse({ error: { message: 'Nope' } }, { status: 403 }))
    await expect(apiFetch('/api/parts')).rejects.toMatchObject({ message: 'Nope' })
  })
})
