import { describe, expect, it } from 'vitest'
import {
  approvalIdentityText,
  approvalTextVariants,
  canonicalFieldAliases,
  collectRecordValues,
  explicitApprovalStatus,
  normalizeAliasName,
  readRecordValue,
} from './approval'

/**
 * QA-FE-01. SolidWorks custom properties arrive as free text, so a part's
 * approval state can be a boolean, a number, "Yes", "APPROVED",
 * "not_approved", a reviewer's name, or blank.
 *
 * The asymmetry matters: showing an unapproved part as approved is the
 * expensive direction, so anything unrecognised must return null (unknown)
 * rather than defaulting either way.
 */

describe('explicitApprovalStatus', () => {
  it.each([true, 1, 'true', 'Yes', 'Y', 'ON', 'approved', 'APPROVED'])(
    'reads %s as approved',
    (value) => {
      expect(explicitApprovalStatus(value)).toBe(true)
    },
  )

  it.each([
    false, 0, 'false', 'No', 'n/a', 'missing', 'none',
    'not approved', 'not_approved', 'not-approved', 'notapproved',
    'unapproved', 'rejected', 'wip',
  ])('reads %s as not approved', (value) => {
    expect(explicitApprovalStatus(value)).toBe(false)
  })

  it.each([null, undefined, '', '   ', 'Jane Doe', 'pending review', {}, []])(
    'returns unknown for %s rather than guessing',
    (value) => {
      expect(explicitApprovalStatus(value)).toBeNull()
    },
  )

  it('never treats an unrecognised word as approved', () => {
    // The direction that matters: a typo must not read as a sign-off.
    expect(explicitApprovalStatus('aproved')).not.toBe(true)
    expect(explicitApprovalStatus('APPROVEDish')).not.toBe(true)
  })

  it('prefers a negative when a value matches both', () => {
    // "not approved" contains "approved"; the negative must win.
    expect(explicitApprovalStatus('not approved')).toBe(false)
  })
})

describe('approvalTextVariants', () => {
  it('normalises separators so all spellings collapse together', () => {
    const variants = approvalTextVariants('Not-Approved')
    expect(variants).toEqual(expect.arrayContaining(['not approved', 'not_approved', 'notapproved']))
  })

  it('returns nothing for empty input', () => {
    expect(approvalTextVariants('')).toEqual([])
    expect(approvalTextVariants('   ')).toEqual([])
  })

  it('lowercases and de-duplicates', () => {
    const variants = approvalTextVariants('APPROVED')
    expect(variants).toContain('approved')
    expect(new Set(variants).size).toBe(variants.length)
  })
})

describe('approvalIdentityText', () => {
  it('returns a reviewer name', () => {
    expect(approvalIdentityText('Jane Doe')).toBe('Jane Doe')
  })

  it('returns nothing for a state word, which is not a person', () => {
    expect(approvalIdentityText('approved')).toBe('')
    expect(approvalIdentityText(true)).toBe('')
  })

  it('joins a list of reviewers', () => {
    expect(approvalIdentityText(['Jane', 'Bob'])).toBe('Jane, Bob')
  })

  it('drops state words from a mixed list', () => {
    expect(approvalIdentityText(['Jane', 'approved'])).toBe('Jane')
  })

  it.each([null, undefined, 42])('returns empty for %s', (value) => {
    expect(approvalIdentityText(value)).toBe('')
  })
})

describe('record helpers', () => {
  it('matches record keys case- and separator-insensitively', () => {
    // Property names come from CAD files with inconsistent casing.
    const record = { 'Part Number': 'PN-1' }
    expect(readRecordValue(record, 'part_number')).toBe('PN-1')
  })

  it('returns undefined for a missing key or record', () => {
    expect(readRecordValue({}, 'nope')).toBeUndefined()
    expect(readRecordValue(null, 'nope')).toBeUndefined()
  })

  it('normalises alias names', () => {
    expect(normalizeAliasName(' Part_Number ')).toBe(normalizeAliasName('part number'))
  })

  it('collects every value an alias list resolves to', () => {
    const record = { pn: 'A', part_number: 'B' }
    expect(collectRecordValues(record, ['pn', 'part_number'])).toEqual(['A', 'B'])
  })

  it('skips aliases with no value', () => {
    expect(collectRecordValues({ pn: 'A' }, ['pn', 'missing'])).toEqual(['A'])
  })

  it('always includes the field id itself', () => {
    expect(canonicalFieldAliases(null, 'material', [])).toContain('material')
  })

  it('merges configured aliases with the fallbacks, de-duplicated', () => {
    const config = { canonical_aliases: [{ field_id: 'material', aliases: ['MATL'] }] }
    const aliases = canonicalFieldAliases(config as never, 'material', ['material', 'Stock'])
    expect(aliases).toEqual(expect.arrayContaining(['material', 'MATL', 'Stock']))
    expect(new Set(aliases).size).toBe(aliases.length)
  })
})
