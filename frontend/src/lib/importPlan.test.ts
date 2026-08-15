import { describe, expect, it } from 'vitest'
import { actionClass, groupOf, resolveModes, valueText, type PlanPartLike } from './importPlan'

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

describe('resolveModes', () => {
  const part = (over: Partial<Parameters<typeof resolveModes>[0]> = {}) =>
    resolveModes({ tier: 'add', ...over })

  it('adds without overwriting by default', () => {
    expect(part()).toEqual({
      data_mode: 'fill_blanks',
      bom_mode: 'fill_if_empty',
      file_mode: 'add_missing',
      approval_mode: 'import_unapproved',
    })
  })

  it('records a release even when adding', () => {
    // Approval comes from CAD, not from TinyMRP. Publishing one destroys
    // nothing, so it must not require the overwrite tier.
    expect(part().approval_mode).toBe('import_unapproved')
  })

  it('lets the pack win on drafts when overwriting', () => {
    expect(part({ tier: 'overwrite' })).toEqual({
      data_mode: 'replace_unapproved',
      bom_mode: 'replace_unapproved',
      file_mode: 'replace_unapproved',
      approval_mode: 'import_unapproved',
    })
  })

  it('only reaches approved data with the permission AND the tick', () => {
    // Either half alone must stay off approved parts: this is the single
    // mapping that stands between a tick and overwriting released data.
    expect(part({ tier: 'overwrite', includeApproved: true }).data_mode).toBe('replace_unapproved')
    expect(part({ tier: 'overwrite', canOverride: true }).data_mode).toBe('replace_unapproved')
    expect(part({ tier: 'overwrite', includeApproved: true, canOverride: true })).toEqual({
      data_mode: 'replace_all',
      bom_mode: 'replace_all',
      file_mode: 'replace_all',
      approval_mode: 'replace_all',
    })
  })

  it('never escalates a category that is not overwriting', () => {
    const modes = part({
      tier: 'overwrite',
      includeApproved: true,
      canOverride: true,
      categories: { data: 'add', file: 'skip' },
    })
    expect(modes.data_mode).toBe('fill_blanks')
    expect(modes.file_mode).toBe('skip')
    expect(modes.bom_mode).toBe('replace_all')
  })

  it('writes no approval at all when properties are skipped', () => {
    expect(part({ tier: 'add', categories: { data: 'skip' } }).approval_mode).toBe('preserve')
  })
})

describe('groupOf', () => {
  const part = (over: Partial<PlanPartLike> = {}): PlanPartLike => ({
    target_state: 'existing_unapproved',
    changed: false,
    blocked: false,
    allowed: true,
    ...over,
  })

  it('puts anything blocked first, whatever else is true of it', () => {
    // A blocked approved part must not hide in "approved changed": the
    // operator is looking for what will not happen.
    expect(groupOf(part({ blocked: true, target_state: 'existing_approved', changed: true }))).toBe('blocked')
    expect(groupOf(part({ allowed: false }))).toBe('blocked')
  })

  it('separates approved parts that are actually changed', () => {
    expect(groupOf(part({ target_state: 'existing_approved', changed: true }))).toBe('modified_approved')
    // Touched but unchanged is not a review item.
    expect(groupOf(part({ target_state: 'existing_approved' }))).toBe('unchanged')
  })

  it('groups new parts and changed drafts apart', () => {
    expect(groupOf(part({ target_state: 'new', changed: true }))).toBe('new')
    expect(groupOf(part({ changed: true }))).toBe('changed')
  })

  it('leaves untouched parts in the tail group', () => {
    expect(groupOf(part())).toBe('unchanged')
  })
})
