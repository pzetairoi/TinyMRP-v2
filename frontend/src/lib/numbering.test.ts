import { describe, expect, it } from 'vitest'
import type { Segment } from './numbering'
import {
  buildSampleNumber,
  cloneSegment,
  createEmptySegment,
  formatDateSample,
  getSegmentKind,
  normalizeSequenceSegments,
  padCounter,
  revisionSample,
  segmentSample,
} from './numbering'

/**
 * QA-FE-01. This builds part numbers, so the invariant in
 * normalizeSequenceSegments is the important one: EXACTLY ONE sequence segment
 * may hold the auto counter. Two would have the server allocate twice per
 * part; none would produce a scheme that never increments.
 */

const seq = (over: Partial<Segment> = {}): Segment => ({
  kind: 'seq', padding: 6, base: 10, start_at: 1, auto_counter: false, ...over,
})

const autoFlags = (items: Segment[]) =>
  items.filter((s) => getSegmentKind(s) === 'seq').map((s) => !!s.auto_counter)

describe('normalizeSequenceSegments', () => {
  it('promotes the first sequence when none is marked auto', () => {
    // A scheme with no auto counter would never increment.
    expect(autoFlags(normalizeSequenceSegments([seq(), seq()]))).toEqual([true, false])
  })

  it('keeps only the first auto counter when several are marked', () => {
    const result = normalizeSequenceSegments([
      seq({ auto_counter: true }),
      seq({ auto_counter: true }),
      seq({ auto_counter: true }),
    ])
    expect(autoFlags(result)).toEqual([true, false, false])
  })

  it('respects an auto counter that is not the first sequence', () => {
    const result = normalizeSequenceSegments([seq(), seq({ auto_counter: true })])
    expect(autoFlags(result)).toEqual([false, true])
  })

  it('leaves a scheme with no sequence segment alone', () => {
    const literals: Segment[] = [{ kind: 'literal', value: 'PART' }]
    expect(normalizeSequenceSegments(literals)).toEqual(literals)
  })

  it('does not mutate the input', () => {
    const input = [seq({ auto_counter: true }), seq({ auto_counter: true })]
    const before = JSON.stringify(input)
    normalizeSequenceSegments(input)
    expect(JSON.stringify(input)).toBe(before)
  })
})

describe('getSegmentKind', () => {
  it.each([
    ['seq', 'seq'],
    ['SEQ', 'seq'],
    ['date', 'date'],
    ['literal', 'literal'],
    ['nonsense', 'literal'],
    [undefined, 'literal'],
  ])('reads %s as %s', (kind, expected) => {
    expect(getSegmentKind({ kind } as Segment)).toBe(expected)
  })
})

describe('padCounter', () => {
  it('pads to the requested width', () => {
    expect(padCounter(7, 6, 10)).toBe('000007')
  })

  it('encodes base 36 in upper case', () => {
    expect(padCounter(36, 4, 36)).toBe('0010')
    expect(padCounter(35, 2, 36)).toBe('0Z')
  })

  it('never produces a zero or negative counter', () => {
    // A part number ending in 000000 would collide on the first allocation.
    expect(padCounter(0, 4, 10)).toBe('0001')
    expect(padCounter(-5, 4, 10)).toBe('0001')
  })

  it('does not truncate a value wider than the padding', () => {
    expect(padCounter(1234567, 3, 10)).toBe('1234567')
  })
})

describe('formatDateSample', () => {
  const now = new Date()
  const yyyy = String(now.getFullYear())

  it.each([
    ['YY', yyyy.slice(-2)],
    ['YYYY', yyyy],
    [undefined, yyyy],
    ['nonsense', yyyy],
  ])('formats %s', (fmt, expected) => {
    expect(formatDateSample(fmt)).toBe(expected)
  })

  it('zero-pads the month', () => {
    expect(formatDateSample('MM')).toMatch(/^\d{2}$/)
    expect(formatDateSample('YYYYMM')).toMatch(/^\d{6}$/)
  })
})

describe('buildSampleNumber', () => {
  it('joins segments with the separator', () => {
    const segments: Segment[] = [
      { kind: 'literal', value: 'PART' },
      seq({ padding: 4, start_at: 12 }),
    ]
    expect(buildSampleNumber(segments, '-')).toBe('PART-0012')
  })

  it('joins with nothing when no separator is given', () => {
    const segments: Segment[] = [{ kind: 'literal', value: 'A' }, { kind: 'literal', value: 'B' }]
    expect(buildSampleNumber(segments, '')).toBe('AB')
  })

  it('drops empty segments so the separator does not double up', () => {
    const segments: Segment[] = [
      { kind: 'literal', value: 'PART' },
      { kind: 'literal', value: '' },
      seq({ padding: 2 }),
    ]
    expect(buildSampleNumber(segments, '-')).toBe('PART-01')
  })
})

describe('segmentSample and createEmptySegment', () => {
  it('samples each kind', () => {
    expect(segmentSample(seq({ padding: 3, start_at: 5 }))).toBe('005')
    expect(segmentSample({ kind: 'literal', value: '  PART  ' })).toBe('PART')
    expect(segmentSample({ kind: 'date', fmt: 'YY' })).toMatch(/^\d{2}$/)
  })

  it('creates a defaulted segment per kind', () => {
    expect(createEmptySegment('seq')).toMatchObject({ padding: 6, base: 10, auto_counter: false })
    expect(createEmptySegment('date')).toMatchObject({ fmt: 'YYYY' })
    expect(createEmptySegment()).toMatchObject({ kind: 'literal', value: '' })
  })

  it('clones without sharing a reference', () => {
    const original = seq()
    const copy = cloneSegment(original)
    expect(copy).not.toBe(original)
    expect(copy).toEqual(original)
  })
})

describe('revisionSample', () => {
  it.each([
    ['alpha', 'a', 'A'],
    ['alpha', undefined, 'A'],
    ['numeric', '5', '5'],
    ['numeric', undefined, '01'],
    ['none', undefined, ''],
    [undefined, undefined, ''],
  ])('policy %s with start %s gives %s', (policy, start, expected) => {
    expect(revisionSample(policy, start)).toBe(expected)
  })
})
