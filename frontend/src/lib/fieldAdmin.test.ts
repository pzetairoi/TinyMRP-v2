import { describe, expect, it } from 'vitest'
import { normalizeSourcePath, parseApprovalRuleValues, slugFieldId } from './fieldAdmin'

/**
 * QA-FE-01. These values are persisted by an administrator and then used to
 * resolve record data, so normalizeSourcePath is a whitelist rather than a
 * tidy-up: only `attrs.*` and `part.*` roots are accepted, and everything else
 * must resolve to '' so a field cannot be pointed at an arbitrary path.
 */

describe('slugFieldId', () => {
  it('lowercases and replaces runs of punctuation with one underscore', () => {
    expect(slugFieldId('Part Number')).toBe('part_number')
    expect(slugFieldId('Weight (kg)')).toBe('weight_kg')
  })

  it('trims leading and trailing underscores', () => {
    expect(slugFieldId('  --Material--  ')).toBe('material')
  })

  it.each([null, undefined, '', '   ', '!!!'])('returns empty for %s', (value) => {
    expect(slugFieldId(value as string)).toBe('')
  })

  it('is idempotent', () => {
    // Re-saving an existing field must not mangle its id.
    const once = slugFieldId('Part Number')
    expect(slugFieldId(once)).toBe(once)
  })
})

describe('normalizeSourcePath', () => {
  it.each([
    ['attrs.material', 'attrs.material'],
    ['part.part_number', 'part.part_number'],
    ['ATTRS.Material', 'attrs.material'],
    ['attrs.Custom Field', 'attrs.custom_field'],
    ['attrs.a.b', 'attrs.a.b'],
  ])('accepts %s as %s', (input, expected) => {
    expect(normalizeSourcePath(input)).toBe(expected)
  })

  it.each([
    'config.secret',
    '__proto__.polluted',
    'user.password',
    'window.location',
  ])('rejects the non-whitelisted root in %s', (input) => {
    // The security property: an unexpected root resolves to nothing rather
    // than being passed through for something else to interpret.
    expect(normalizeSourcePath(input)).toBe('')
  })

  it.each(['attrs', 'part', '', '   ', '...', 'attrs.'])(
    'rejects %s for having no usable leaf',
    (input) => {
      expect(normalizeSourcePath(input)).toBe('')
    },
  )

  it('ignores empty segments from doubled dots', () => {
    expect(normalizeSourcePath('attrs..material')).toBe('attrs.material')
  })
})

describe('parseApprovalRuleValues', () => {
  it.each([',', ';', '\n'])('splits on %s', (separator) => {
    expect(parseApprovalRuleValues(`Yes${separator}Approved`)).toEqual(['yes', 'approved'])
  })

  it('normalises separators and casing so spellings compare equal', () => {
    expect(parseApprovalRuleValues('Not_Approved, NOT-APPROVED')).toEqual(['not approved'])
  })

  it('de-duplicates while preserving first-seen order', () => {
    expect(parseApprovalRuleValues('b, a, b')).toEqual(['b', 'a'])
  })

  it('returns nothing for blank input', () => {
    expect(parseApprovalRuleValues('')).toEqual([])
    expect(parseApprovalRuleValues(' , ; ')).toEqual([])
  })
})
