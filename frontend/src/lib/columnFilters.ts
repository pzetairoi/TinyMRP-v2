import { FilterMatchMode } from 'primereact/api'
import type { DataTableFilterMeta } from 'primereact/datatable'
import type { FieldDefinition } from './fieldConfig'

/**
 * Column-filter defaults and normalisation for the parts table.
 *
 * Extracted from PartsPage so the normalisation can be tested directly: it
 * has to cope with filter metas persisted by older builds, and getting that
 * wrong silently drops a user's saved filters.
 */

export function defaultColumnMatchMode(field: FieldDefinition) {
  if (field.data_type === 'boolean' || field.data_type === 'number') return FilterMatchMode.EQUALS
  if (field.data_type === 'date') return FilterMatchMode.DATE_IS
  return FilterMatchMode.CONTAINS
}

export function defaultColumnFilterMeta(field: FieldDefinition) {
  return {
    value: field.data_type === 'boolean' ? null : '',
    matchMode: defaultColumnMatchMode(field),
  }
}

export function ensureColumnFilters(filters: DataTableFilterMeta, fields: FieldDefinition[]) {
  let changed = false
  const next = { ...filters } as DataTableFilterMeta

  for (const field of fields) {
    if (field.filterable === false) continue
    const current = (next as any)?.[field.id]
    // Unwrap leftover menu-style metas ({operator, constraints}) into flat {value, matchMode}.
    const flat = current && typeof current === 'object' && Array.isArray(current.constraints)
      ? current.constraints[0]
      : current
    const normalized = {
      ...defaultColumnFilterMeta(field),
      ...(flat && typeof flat === 'object' && 'value' in flat
        ? { value: flat.value ?? defaultColumnFilterMeta(field).value }
        : {}),
    }
    if (
      current === flat &&
      current?.value === normalized.value &&
      current?.matchMode === normalized.matchMode
    ) continue
    ;(next as any)[field.id] = normalized
    changed = true
  }

  return changed ? next : filters
}
