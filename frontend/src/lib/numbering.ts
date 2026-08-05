export type Segment = {
  kind?: string
  value?: string
  padding?: number
  base?: number
  start_at?: number
  auto_counter?: boolean
  fmt?: string
}

export type SegmentKind = 'literal' | 'seq' | 'date'


/**
 * Part-numbering scheme preview and normalisation.
 *
 * Extracted from AdminAddinPage. The invariant that matters is in
 * normalizeSequenceSegments: exactly one sequence segment may hold the auto
 * counter. Two would let the server allocate twice per part, and none would
 * produce a scheme that never increments.
 */

export function getSegmentKind(segment?: Segment): SegmentKind {
  const kind = (segment?.kind || '').trim().toLowerCase()
  if (kind === 'seq' || kind === 'date') return kind
  return 'literal'
}

export function createEmptySegment(kind: SegmentKind = 'literal'): Segment {
  if (kind === 'seq') return { kind: 'seq', padding: 6, base: 10, start_at: 1, auto_counter: false }
  if (kind === 'date') return { kind: 'date', fmt: 'YYYY' }
  return { kind: 'literal', value: '' }
}

export function cloneSegment(segment?: Segment): Segment {
  const kind = getSegmentKind(segment)
  return { ...createEmptySegment(kind), ...(segment || {}), kind }
}

export function normalizeSequenceSegments(items: Segment[]) {
  const next = items.map(cloneSegment)
  const sequenceIndexes = next
    .map((segment, index) => ({ segment, index }))
    .filter(({ segment }) => getSegmentKind(segment) === 'seq')
    .map(({ index }) => index)

  if (!sequenceIndexes.length) {
    return next
  }

  let autoIndex = -1
  sequenceIndexes.forEach((index) => {
    if (!next[index].auto_counter) return
    if (autoIndex === -1) {
      autoIndex = index
      return
    }
    next[index] = { ...next[index], auto_counter: false }
  })

  if (autoIndex === -1) {
    const first = sequenceIndexes[0]
    next[first] = { ...next[first], auto_counter: true }
  }

  return next
}

export function padCounter(value: number, width: number, base: number) {
  const safe = Math.max(1, Math.floor(value) || 1)
  const text = base === 36 ? safe.toString(36).toUpperCase() : String(safe)
  return text.padStart(Math.max(width, 1), '0')
}

export function formatDateSample(fmt?: string) {
  const now = new Date()
  const yyyy = String(now.getFullYear())
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  if (fmt === 'YY') return yyyy.slice(-2)
  if (fmt === 'MM') return mm
  if (fmt === 'YYYYMM') return `${yyyy}${mm}`
  return yyyy
}

export function segmentSample(segment: Segment): string {
  const kind = getSegmentKind(segment)
  if (kind === 'seq') return padCounter(segment.start_at ?? 1, segment.padding ?? 6, segment.base ?? 10)
  if (kind === 'date') return formatDateSample(segment.fmt)
  return (segment.value || '').trim()
}

export function buildSampleNumber(segments: Segment[], separator: string) {
  const pieces = segments.map(segmentSample).filter(Boolean)
  return pieces.join(separator || '')
}

export function revisionSample(policy?: string, start?: string) {
  const p = (policy || 'none').toLowerCase()
  if (p === 'alpha') return (start || 'A').toUpperCase()
  if (p === 'numeric') return start && start.trim() ? start.trim() : '01'
  return ''
}
