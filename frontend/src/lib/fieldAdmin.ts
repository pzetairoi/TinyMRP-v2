/**
 * Field-administration input normalisation.
 *
 * Extracted from AdminFieldsPage because these values are persisted and then
 * used to resolve record data. normalizeSourcePath in particular is a
 * whitelist: only `attrs.*` and `part.*` roots are accepted, so an operator
 * cannot point a field at an arbitrary path.
 */

export function slugFieldId(value: string) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

export function normalizeSourcePath(value: string) {
  const parts = String(value || '')
    .split('.')
    .map((part) => String(part || '').trim())
    .filter(Boolean)
  if (parts.length < 2) return ''
  const [head, ...tail] = parts
  if (!['attrs', 'part'].includes(head.toLowerCase())) return ''
  const normalizedTail = tail.map((part) => slugFieldId(part)).filter(Boolean)
  if (!normalizedTail.length) return ''
  return [head.toLowerCase(), ...normalizedTail].join('.')
}

export function parseApprovalRuleValues(value: string) {
  return value
    .split(/[,;\n]/)
    .map((item) => item.trim().toLowerCase().replace(/[_-]+/g, ' ').replace(/\s+/g, ' '))
    .filter((item, index, values) => item && values.indexOf(item) === index)
}
