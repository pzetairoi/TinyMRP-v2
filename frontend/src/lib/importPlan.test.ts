import { describe, expect, it } from 'vitest'
import { actionClass, valueText } from './importPlan'

/**
 * QA-FE-01. The import plan is how an operator decides whether to run an
 * import against live data. A value rendered as a blank cell, or a destructive
 * action coloured as if it were safe, both corrupt that decision.
 */

describe('valueText', () => {
  it.each([null, undefined, ''])('renders %s as a dash rather than a blank cell', (value) => {
    // An empty cell is ambiguous: "no value" and "we failed to read it" must
    // not look identical in a preview that authorises a write.
    expect(valueText(value)).toBe('—')
  })

  it('passes strings through unchanged', () => {
    expect(valueText('Bracket')).toBe('Bracket')
  })

  it('keeps falsy-but-meaningful values visible', () => {
    expect(valueText(0)).toBe('0')
    expect(valueText(false)).toBe('false')
  })

  it('serialises objects and arrays', () => {
    expect(valueText({ a: 1 })).toBe('{"a":1}')
    expect(valueText([1, 2])).toBe('[1,2]')
  })

  it('survives a circular structure', () => {
    const circular: Record<string, unknown> = {}
    circular.self = circular
    expect(valueText(circular)).toBeTruthy()
  })
})

describe('actionClass', () => {
  it('marks additions as safe', () => {
    expect(actionClass('add')).toBe('text-success')
  })

  it.each(['remove', 'replace', 'clear'])('marks %s as destructive', (action) => {
    // These overwrite or delete existing data; they must never read as safe.
    expect(actionClass(action)).toBe('text-danger')
  })

  it.each(['blocked', 'skipped'])('marks %s as a warning', (action) => {
    expect(actionClass(action)).toBe('text-warning')
  })

  it.each(['change', 'quantity_change'])('marks %s as informational', (action) => {
    expect(actionClass(action)).toBe('text-primary')
  })

  it('falls back to muted for an unknown action', () => {
    // A new backend action must not accidentally inherit "safe" green.
    expect(actionClass('some_future_action')).toBe('text-muted')
  })
})
