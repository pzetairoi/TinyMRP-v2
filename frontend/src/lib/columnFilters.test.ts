import { FilterMatchMode } from 'primereact/api'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { describe, expect, it } from 'vitest'
import type { FieldDefinition } from './fieldConfig'
import { defaultColumnFilterMeta, defaultColumnMatchMode, ensureColumnFilters } from './columnFilters'

/**
 * QA-FE-01. This normalisation has to cope with filter metas persisted by
 * older builds. Getting it wrong silently drops a user's saved filters, or
 * feeds PrimeReact a shape it ignores - both look like "search is broken".
 */

const field = (id: string, dataType?: string, over: Partial<FieldDefinition> = {}) =>
  ({ id, label: id, data_type: dataType, ...over }) as unknown as FieldDefinition

describe('defaultColumnMatchMode', () => {
  it.each([
    ['boolean', FilterMatchMode.EQUALS],
    ['number', FilterMatchMode.EQUALS],
    ['date', FilterMatchMode.DATE_IS],
    ['string', FilterMatchMode.CONTAINS],
    [undefined, FilterMatchMode.CONTAINS],
  ])('maps %s to %s', (dataType, expected) => {
    expect(defaultColumnMatchMode(field('f', dataType as string))).toBe(expected)
  })
})

describe('defaultColumnFilterMeta', () => {
  it('starts booleans at null so "unset" differs from "false"', () => {
    // '' would be coerced to false and silently filter out every true row.
    expect(defaultColumnFilterMeta(field('f', 'boolean')).value).toBeNull()
  })

  it('starts other types at an empty string', () => {
    expect(defaultColumnFilterMeta(field('f', 'string')).value).toBe('')
  })
})

describe('ensureColumnFilters', () => {
  it('adds a default meta for a field that has none', () => {
    const next = ensureColumnFilters({} as DataTableFilterMeta, [field('pn', 'string')])
    expect(next).toMatchObject({ pn: { value: '', matchMode: FilterMatchMode.CONTAINS } })
  })

  it('skips fields marked unfilterable', () => {
    const next = ensureColumnFilters({} as DataTableFilterMeta, [
      field('pn', 'string', { filterable: false }),
    ])
    expect(next).toEqual({})
  })

  it('preserves a value the user already typed', () => {
    const existing = { pn: { value: 'bolt', matchMode: FilterMatchMode.CONTAINS } }
    const next = ensureColumnFilters(existing as DataTableFilterMeta, [field('pn', 'string')])
    expect((next as any).pn.value).toBe('bolt')
  })

  it('flattens a legacy menu-style meta into the flat shape', () => {
    // Older builds persisted {operator, constraints:[...]}, which the current
    // table ignores - the user would see their filter vanish.
    const legacy = {
      pn: { operator: 'and', constraints: [{ value: 'bolt', matchMode: FilterMatchMode.CONTAINS }] },
    }
    const next = ensureColumnFilters(legacy as unknown as DataTableFilterMeta, [field('pn', 'string')])
    expect((next as any).pn).toMatchObject({ value: 'bolt', matchMode: FilterMatchMode.CONTAINS })
    expect((next as any).pn.constraints).toBeUndefined()
  })

  it('returns the SAME object when nothing changed', () => {
    // Referential identity matters: a new object every render would retrigger
    // the effect that calls this and loop.
    const stable = { pn: { value: '', matchMode: FilterMatchMode.CONTAINS } }
    const next = ensureColumnFilters(stable as DataTableFilterMeta, [field('pn', 'string')])
    expect(next).toBe(stable)
  })

  it('leaves unrelated keys untouched', () => {
    const existing = { global: { value: 'x', matchMode: FilterMatchMode.CONTAINS } }
    const next = ensureColumnFilters(existing as DataTableFilterMeta, [field('pn', 'string')])
    expect((next as any).global.value).toBe('x')
  })
})
