import { describe, expect, it } from 'vitest'
import { isCancelledRequest } from './api'

/**
 * Reported: "network error" appeared every time a link in the BOM table was
 * used, and the server log showed nothing at all - because nothing had gone
 * wrong.
 *
 * The BOM table links are plain anchors, so clicking one is a FULL page load.
 * The browser tears down in-flight requests without React ever unmounting, the
 * rejection lands while the old page is still on screen, and it was rendered as
 * a failure. Firefox words it "NetworkError when attempting to fetch resource".
 */
describe('isCancelledRequest', () => {
  it('recognises a request killed by navigating away in Firefox', () => {
    expect(isCancelledRequest(new TypeError('NetworkError when attempting to fetch resource.'))).toBe(true)
  })

  it('recognises the Chrome and Safari wordings too', () => {
    expect(isCancelledRequest(new TypeError('Failed to fetch'))).toBe(true)
    expect(isCancelledRequest(new TypeError('Load failed'))).toBe(true)
  })

  it('recognises an explicit abort', () => {
    const err = new Error('aborted')
    err.name = 'AbortError'
    expect(isCancelledRequest(err)).toBe(true)
  })

  it('does NOT swallow a real server failure', () => {
    // The whole point: an outage must still reach the user, because they are
    // not going anywhere and the message is the only thing they will see.
    expect(isCancelledRequest({ message: 'Request failed (500)' })).toBe(false)
    expect(isCancelledRequest({ message: 'Permission denied.' })).toBe(false)
    expect(isCancelledRequest({ message: 'Invalid JSON response: SyntaxError' })).toBe(false)
  })

  it('tolerates junk instead of throwing', () => {
    expect(isCancelledRequest(null)).toBe(false)
    expect(isCancelledRequest('boom')).toBe(false)
    expect(isCancelledRequest(undefined)).toBe(false)
  })
})
