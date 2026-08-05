import { describe, expect, it } from 'vitest'
import { formatBytes, groupFiles, groupKeyOf, hasDisplayValue } from './fileDisplay'

/**
 * QA-FE-01. SolidWorks emits several extensions for one logical artefact, so
 * grouping is what makes the files panel show one row per artefact instead of
 * one per extension. Getting it wrong duplicates rows or hides a deliverable.
 */

describe('groupKeyOf', () => {
  it.each([
    ['eprt', 'edr'],
    ['edr', 'edr'],
    ['stp', 'step'],
    ['step', 'step'],
    ['jpg', 'png'],
    ['jpeg', 'png'],
    ['png', 'png'],
  ])('collapses %s into the %s group', (ext, expected) => {
    expect(groupKeyOf({ ext })).toBe(expected)
  })

  it('is case-insensitive', () => {
    expect(groupKeyOf({ ext: 'STEP' })).toBe('step')
  })

  it('prefers ext_group over group over ext', () => {
    expect(groupKeyOf({ ext_group: 'pdf', group: 'dxf', ext: 'png' })).toBe('pdf')
    expect(groupKeyOf({ group: 'dxf', ext: 'png' })).toBe('dxf')
  })

  it('falls back to "others" when nothing identifies the file', () => {
    expect(groupKeyOf({})).toBe('others')
  })

  it('passes unrecognised extensions through unchanged', () => {
    expect(groupKeyOf({ ext: 'dxf' })).toBe('dxf')
  })
})

describe('groupFiles', () => {
  it('buckets files by their resolved group', () => {
    const grouped = groupFiles([{ ext: 'stp' }, { ext: 'step' }, { ext: 'pdf' }])
    expect(grouped.step).toHaveLength(2)
    expect(grouped.pdf).toHaveLength(1)
  })

  it('tolerates an empty or missing list', () => {
    expect(groupFiles([])).toEqual({})
    expect(groupFiles(undefined as never)).toEqual({})
  })
})

describe('formatBytes', () => {
  it.each([
    [0, '-'],
    [undefined, '-'],
    [512, '512 B'],   // >= 10, so no decimal
    [1024, '1.0 KB'],
    [1536, '1.5 KB'],
    [1048576, '1.0 MB'],
  ])('formats %s as %s', (input, expected) => {
    expect(formatBytes(input as number)).toBe(expected)
  })

  it('drops the decimal once the number is large enough to be unhelpful', () => {
    expect(formatBytes(20 * 1024)).toBe('20 KB')
  })

  it('stops scaling at GB', () => {
    expect(formatBytes(5 * 1024 ** 4)).toContain('GB')
  })
})

describe('hasDisplayValue', () => {
  it.each([null, undefined, '', '   ', [], {}])('treats %s as nothing to show', (value) => {
    expect(hasDisplayValue(value)).toBe(false)
  })

  it.each([0, false, 'text', [1], { a: 1 }])('treats %s as displayable', (value) => {
    // 0 and false are falsy but meaningful - a quantity of zero is a value.
    expect(hasDisplayValue(value)).toBe(true)
  })
})
