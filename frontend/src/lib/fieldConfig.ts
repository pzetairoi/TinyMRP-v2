import { apiFetch } from './api'

export type FieldDefinition = {
  id: string
  label: string
  arena_header?: string
  kind: string
  data_type?: string
  source_path?: string
  source_locked?: boolean
  sortable?: boolean
  filterable?: boolean
}

export type FieldCandidate = {
  id: string
  label: string
  source_path: string
  data_type?: string
  part_count: number
  sample_value?: string
  raw_keys?: string[]
}

export type FieldContext = {
  label: string
  required_field_ids: string[]
  allowed_field_ids: string[]
  default_field_ids: string[]
  available_fields: FieldDefinition[]
}

export type CanonicalAliasEntry = {
  field_id: string
  label: string
  multi_value?: boolean
  aliases: string[]
}

export type ApprovalRules = {
  approved_values: string[]
  unapproved_values: string[]
  identity_placeholders: string[]
}

export type FieldPreferences = {
  contexts: Record<string, { field_ids: string[]; use_default?: boolean }>
}

export type FieldConfigPayload = {
  fields: FieldDefinition[]
  contexts: Record<string, FieldContext>
  canonical_aliases?: CanonicalAliasEntry[]
  approval_rules?: ApprovalRules
}

export type FieldConfigResponse = {
  ok: boolean
  config: FieldConfigPayload
  user_preferences: FieldPreferences
  permissions: { can_admin: boolean }
}

export async function loadFieldConfig() {
  return apiFetch<FieldConfigResponse>('/api/field-config')
}

export async function loadFieldCandidates() {
  return apiFetch<{ ok: boolean; candidates: FieldCandidate[] }>('/api/admin/field-config/candidates')
}

export function contextFields(config: FieldConfigPayload | null | undefined, contextName: string): FieldDefinition[] {
  return config?.contexts?.[contextName]?.available_fields || []
}

export function defaultFieldIds(config: FieldConfigPayload | null | undefined, contextName: string): string[] {
  return config?.contexts?.[contextName]?.default_field_ids || []
}

export function requiredFieldIds(config: FieldConfigPayload | null | undefined, contextName: string): string[] {
  return config?.contexts?.[contextName]?.required_field_ids || []
}

export function selectedFieldIds(
  config: FieldConfigPayload | null | undefined,
  prefs: FieldPreferences | null | undefined,
  contextName: string,
) {
  const allowed = config?.contexts?.[contextName]?.allowed_field_ids || []
  const fallback = defaultFieldIds(config, contextName)
  const required = new Set(requiredFieldIds(config, contextName))
  const selected = prefs?.contexts?.[contextName]?.field_ids?.length ? (prefs?.contexts?.[contextName]?.field_ids || []) : fallback
  const next: string[] = []
  for (const fieldId of selected) {
    if (!allowed.includes(fieldId) || next.includes(fieldId)) continue
    next.push(fieldId)
  }
  for (const fieldId of required) {
    if (!next.includes(fieldId) && allowed.includes(fieldId)) next.unshift(fieldId)
  }
  return next
}

export function updateContextSelection(
  config: FieldConfigPayload | null | undefined,
  prefs: FieldPreferences | null | undefined,
  contextName: string,
  fieldIds: string[],
): FieldPreferences {
  const allowed = new Set(config?.contexts?.[contextName]?.allowed_field_ids || [])
  const required = requiredFieldIds(config, contextName)
  const nextIds: string[] = []
  for (const fieldId of fieldIds) {
    if (!allowed.has(fieldId) || nextIds.includes(fieldId)) continue
    nextIds.push(fieldId)
  }
  for (const fieldId of required) {
    if (allowed.has(fieldId) && !nextIds.includes(fieldId)) nextIds.unshift(fieldId)
  }
  return {
    contexts: {
      ...(prefs?.contexts || {}),
      [contextName]: {
        ...(prefs?.contexts?.[contextName] || {}),
        field_ids: nextIds,
      },
    },
  }
}

export function updateContextMode(
  prefs: FieldPreferences | null | undefined,
  contextName: string,
  useDefault: boolean,
): FieldPreferences {
  return {
    contexts: {
      ...(prefs?.contexts || {}),
      [contextName]: {
        ...(prefs?.contexts?.[contextName] || { field_ids: [] }),
        use_default: useDefault,
      },
    },
  }
}

export async function saveFieldPreferences(fieldPreferences: FieldPreferences) {
  return apiFetch<{ ok: boolean; settings: { field_preferences: FieldPreferences } }>('/api/me/settings', {
    method: 'PUT',
    body: JSON.stringify({ field_preferences: fieldPreferences }),
  })
}

export function fieldValue(row: Record<string, any> | null | undefined, fieldId: string) {
  return row?.[fieldId]
}

function normalizeText(value: any) {
  return String(value ?? '').trim().toLowerCase()
}

function parseBoolFilter(value: any): boolean | null {
  const text = normalizeText(value)
  if (!text) return null
  if (['1', 'true', 'yes', 'y', 'on'].includes(text)) return true
  if (['0', 'false', 'no', 'n', 'off', 'missing'].includes(text)) return false
  return null
}

function parseNumber(value: any): number | null {
  const text = String(value ?? '').trim()
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

function containsAllTerms(value: any, filterValue: any) {
  const text = normalizeText(filterValue)
  if (!text) return true
  const hay = normalizeText(value)
  const terms = text.split(/\s+/).filter(Boolean)
  return terms.every((term) => hay.includes(term))
}

function unwrapFilterValue(filterValue: any): any {
  if (!filterValue || typeof filterValue !== 'object') return filterValue
  if (Array.isArray(filterValue)) return filterValue
  if ('value' in filterValue) return unwrapFilterValue(filterValue.value)
  if (Array.isArray(filterValue.constraints) && filterValue.constraints.length) {
    return unwrapFilterValue(filterValue.constraints[0])
  }
  return filterValue
}

export function fieldFilterPlaceholder(field: FieldDefinition) {
  if (field.data_type === 'boolean') return 'true / false'
  if (field.data_type === 'number') return 'e.g. >10 or 5..15'
  return field.label
}

export function matchesFieldFilter(field: FieldDefinition, value: any, filterValue: any) {
  const normalizedFilterValue = unwrapFilterValue(filterValue)
  const text = String(normalizedFilterValue ?? '').trim()
  if (!text) return true
  if (field.data_type === 'boolean') {
    const expected = parseBoolFilter(normalizedFilterValue)
    if (expected !== null) return Boolean(value) === expected
    return containsAllTerms(value ? 'true yes' : 'false no', text)
  }
  if (field.data_type === 'number') {
    const actual = parseNumber(value)
    if (actual === null) return false
    const range = text.match(/^\s*(-?\d+(?:\.\d+)?)\s*(?:\.\.|to|-)\s*(-?\d+(?:\.\d+)?)\s*$/i)
    if (range) {
      const left = Number(range[1])
      const right = Number(range[2])
      return actual >= Math.min(left, right) && actual <= Math.max(left, right)
    }
    const compare = text.match(/^\s*(<=|>=|=|<|>)?\s*(-?\d+(?:\.\d+)?)\s*$/)
    if (compare) {
      const op = compare[1] || '='
      const target = Number(compare[2])
      if (op === '>') return actual > target
      if (op === '>=') return actual >= target
      if (op === '<') return actual < target
      if (op === '<=') return actual <= target
      return actual === target
    }
  }
  return containsAllTerms(value, text)
}

export function formatFieldValue(value: any) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (Array.isArray(value)) return value.join(', ')
  return String(value)
}
