import { describe, expect, it } from 'vitest'
import { effectiveRevisionFor, revisionFromLocation } from './partIdentity'

/**
 * Reported from a live instance: clicking a BOM child produced a page of 404s
 * while the address bar showed the right part.
 *
 * Cause: navigating between parts does not unmount the detail page, so the
 * previously-loaded part stayed in state and supplied ITS revision to every
 * request for the new part. Landing on a child whose revision is blank, from a
 * parent at revision "1", meant every call went out with rev=1 and missed.
 */
describe('effectiveRevisionFor', () => {
  it('ignores a stale part left over from the previous navigation', () => {
    const stale = { part_number: 'J200684', revision: '1' }
    // The BOM child has a blank revision; the parent had "1".
    expect(effectiveRevisionFor('AWS-Z-009025', '', stale)).toBe('')
  })

  it('uses the loaded revision once the part matches', () => {
    const loaded = { part_number: 'AWS-Z-009025', revision: 'B' }
    expect(effectiveRevisionFor('AWS-Z-009025', '', loaded)).toBe('B')
  })

  it('matches part numbers case-insensitively, as the backend does', () => {
    const loaded = { part_number: 'aws-z-009025', revision: 'B' }
    expect(effectiveRevisionFor('AWS-Z-009025', '', loaded)).toBe('B')
  })

  it('falls back to the URL revision before anything is loaded', () => {
    expect(effectiveRevisionFor('J200684', '1', null)).toBe('1')
  })

  it('prefers the URL revision over a matching part with no revision', () => {
    const loaded = { part_number: 'J200684' }
    expect(effectiveRevisionFor('J200684', '1', loaded)).toBe('1')
  })
})

describe('revisionFromLocation', () => {
  const stale = { pn: 'J200684', rev: '1' }

  it('respects an EMPTY rev parameter instead of falling back', () => {
    // The bug: "" is falsy, so `sp.get("rev") || initial.rev` reached past a
    // meaningful blank and used the revision of whichever page loaded first.
    expect(revisionFromLocation('?rev=', 'AWS-Z-009025', stale)).toBe('')
  })

  it('uses the parameter when it has a value', () => {
    expect(revisionFromLocation('?rev=B', 'AWS-Z-009025', stale)).toBe('B')
  })

  it('falls back only when the parameter is absent AND the part matches', () => {
    expect(revisionFromLocation('', 'J200684', stale)).toBe('1')
  })

  it('ignores server state describing a different part', () => {
    expect(revisionFromLocation('', 'AWS-Z-009025', stale)).toBe('')
  })

  it('matches the part case-insensitively, as the backend does', () => {
    expect(revisionFromLocation('', 'j200684', stale)).toBe('1')
  })

  it('tolerates missing server state', () => {
    expect(revisionFromLocation('', 'J200684', null)).toBe('')
  })
})
