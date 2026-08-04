import { describe, expect, it } from 'vitest'
import type { FieldConfigPayload, FieldDefinition, FieldPreferences } from './fieldConfig'
import {
  formatFieldValue,
  matchesFieldFilter,
  reviewColumnVisible,
  selectedFieldIds,
  updateContextSelection,
} from './fieldConfig'

/**
 * QA-FE-01. Field configuration decides which columns a user sees, so its
 * rules are a presentation-level access control: a field the backend did not
 * allow must never appear because a stale preference asked for it.
 */

const config = {
  contexts: {
    parts: {
      available_fields: [],
      allowed_field_ids: ['pn', 'rev', 'desc', 'qty', 'cost'],
      default_field_ids: ['pn', 'rev', 'desc'],
      required_field_ids: ['pn'],
    },
  },
} as unknown as FieldConfigPayload

function prefsWith(fieldIds: string[]): FieldPreferences {
  return { contexts: { parts: { field_ids: fieldIds } } } as unknown as FieldPreferences
}

function field(dataType: string): FieldDefinition {
  return { id: 'f', label: 'F', data_type: dataType } as unknown as FieldDefinition
}

describe('selectedFieldIds', () => {
  it('falls back to the defaults when no preference is stored', () => {
    expect(selectedFieldIds(config, null, 'parts')).toEqual(['pn', 'rev', 'desc'])
  })

  it('honours a stored preference', () => {
    expect(selectedFieldIds(config, prefsWith(['pn', 'qty']), 'parts')).toEqual(['pn', 'qty'])
  })

  it('drops fields the backend does not allow', () => {
    // The rule that matters: a stale or tampered preference cannot surface a
    // column the server withheld (e.g. cost data for a restricted role).
    const result = selectedFieldIds(config, prefsWith(['pn', 'secret_margin']), 'parts')
    expect(result).not.toContain('secret_margin')
    expect(result).toEqual(['pn'])
  })

  it('always includes required fields even if the preference omits them', () => {
    expect(selectedFieldIds(config, prefsWith(['qty']), 'parts')).toContain('pn')
  })

  it('de-duplicates repeated field ids', () => {
    expect(selectedFieldIds(config, prefsWith(['pn', 'pn', 'qty']), 'parts')).toEqual(['pn', 'qty'])
  })

  it('returns an empty list for an unknown context rather than throwing', () => {
    expect(selectedFieldIds(config, null, 'nope')).toEqual([])
  })

  it('tolerates a null config', () => {
    expect(selectedFieldIds(null, prefsWith(['pn']), 'parts')).toEqual([])
  })
})

describe('updateContextSelection', () => {
  it('stores the selection for the context', () => {
    const next = updateContextSelection(config, null, 'parts', ['pn', 'qty'])
    expect(next.contexts?.parts?.field_ids).toEqual(['pn', 'qty'])
  })

  it('refuses to store a disallowed field', () => {
    const next = updateContextSelection(config, null, 'parts', ['pn', 'not_allowed'])
    expect(next.contexts?.parts?.field_ids).toEqual(['pn'])
  })

  it('re-adds a required field the user tried to remove', () => {
    const next = updateContextSelection(config, null, 'parts', ['qty'])
    expect(next.contexts?.parts?.field_ids).toContain('pn')
  })

  it('leaves other contexts untouched', () => {
    const existing = { contexts: { orders: { field_ids: ['a'] } } } as unknown as FieldPreferences
    const next = updateContextSelection(config, existing, 'parts', ['pn'])
    expect(next.contexts?.orders?.field_ids).toEqual(['a'])
  })

  it('does not mutate the incoming preferences', () => {
    const existing = prefsWith(['pn'])
    const before = JSON.stringify(existing)
    updateContextSelection(config, existing, 'parts', ['pn', 'qty'])
    expect(JSON.stringify(existing)).toBe(before)
  })
})

describe('matchesFieldFilter - text', () => {
  const text = field('string')

  it('matches everything when the filter is empty', () => {
    expect(matchesFieldFilter(text, 'anything', '')).toBe(true)
    expect(matchesFieldFilter(text, 'anything', null)).toBe(true)
  })

  it('is case-insensitive and substring based', () => {
    expect(matchesFieldFilter(text, 'Hex Bolt M8', 'hex')).toBe(true)
  })

  it('requires ALL space-separated terms', () => {
    expect(matchesFieldFilter(text, 'Hex Bolt M8', 'bolt m8')).toBe(true)
    expect(matchesFieldFilter(text, 'Hex Bolt M8', 'bolt m10')).toBe(false)
  })

  it('matches terms in any order', () => {
    expect(matchesFieldFilter(text, 'Hex Bolt M8', 'm8 hex')).toBe(true)
  })

  it('treats null values as empty rather than throwing', () => {
    expect(matchesFieldFilter(text, null, 'x')).toBe(false)
  })
})

describe('matchesFieldFilter - number', () => {
  const num = field('number')

  it('matches an exact value', () => {
    expect(matchesFieldFilter(num, 10, '10')).toBe(true)
    expect(matchesFieldFilter(num, 11, '10')).toBe(false)
  })

  it.each([
    ['>5', 10, true],
    ['>15', 10, false],
    ['>=10', 10, true],
    ['<20', 10, true],
    ['<=9', 10, false],
  ])('supports the comparator %s', (filter, value, expected) => {
    expect(matchesFieldFilter(num, value, filter)).toBe(expected)
  })

  it.each([
    ['5..15', 10, true],
    ['5 to 15', 10, true],
    ['5-15', 10, true],
    ['1..5', 10, false],
  ])('supports the range %s', (filter, value, expected) => {
    expect(matchesFieldFilter(num, value, filter)).toBe(expected)
  })

  it('accepts an inverted range', () => {
    expect(matchesFieldFilter(num, 10, '15..5')).toBe(true)
  })

  it('excludes rows with no numeric value', () => {
    expect(matchesFieldFilter(num, null, '>0')).toBe(false)
    expect(matchesFieldFilter(num, 'n/a', '>0')).toBe(false)
  })

  it('handles negatives and decimals', () => {
    expect(matchesFieldFilter(num, -2.5, '<0')).toBe(true)
    expect(matchesFieldFilter(num, 2.5, '2.5')).toBe(true)
  })
})

describe('matchesFieldFilter - boolean', () => {
  const bool = field('boolean')

  it.each(['1', 'true', 'yes', 'y', 'on'])('treats %s as true', (filter) => {
    expect(matchesFieldFilter(bool, true, filter)).toBe(true)
    expect(matchesFieldFilter(bool, false, filter)).toBe(false)
  })

  it.each(['0', 'false', 'no', 'n', 'off', 'missing'])('treats %s as false', (filter) => {
    expect(matchesFieldFilter(bool, false, filter)).toBe(true)
    expect(matchesFieldFilter(bool, true, filter)).toBe(false)
  })

  it('coerces truthy values consistently', () => {
    expect(matchesFieldFilter(bool, 'anything', 'yes')).toBe(true)
    expect(matchesFieldFilter(bool, '', 'no')).toBe(true)
  })
})

describe('formatFieldValue', () => {
  it.each([null, undefined, ''])('renders %s as a dash', (value) => {
    expect(formatFieldValue(value)).toBe('-')
  })

  it('renders booleans as Yes/No', () => {
    expect(formatFieldValue(true)).toBe('Yes')
    expect(formatFieldValue(false)).toBe('No')
  })

  it('joins arrays', () => {
    expect(formatFieldValue(['a', 'b'])).toBe('a, b')
  })

  it('keeps zero visible rather than showing a dash', () => {
    // 0 is falsy but meaningful for a quantity.
    expect(formatFieldValue(0)).toBe('0')
  })
})

describe('reviewColumnVisible', () => {
  it('defaults to visible', () => {
    expect(reviewColumnVisible(null, 'parts')).toBe(true)
  })

  it('is hidden only when explicitly false', () => {
    const prefs = { review_columns: { parts: false } } as unknown as FieldPreferences
    expect(reviewColumnVisible(prefs, 'parts')).toBe(false)
  })
})
