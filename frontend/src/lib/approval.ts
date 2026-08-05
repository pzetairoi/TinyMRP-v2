import type { FieldConfigPayload } from './fieldConfig'

/**
 * Approval-state interpretation for part detail.
 *
 * SolidWorks custom properties arrive as free text, so "approved" can be a
 * boolean, a number, "Yes", "APPROVED", "not_approved", a reviewer's name, or
 * blank. Reading one of those wrongly shows a part as approved when it is not,
 * which is the expensive direction to get wrong.
 *
 * Extracted from PartDetailPage so it is testable on its own.
 */

const APPROVAL_TRUE_VALUES = new Set(["1", "true", "yes", "y", "on", "approved"])
const APPROVAL_FALSE_VALUES = new Set([
  "0",
  "false",
  "no",
  "n",
  "off",
  "missing",
  "none",
  "absent",
  "n/a",
  "na",
  "null",
  "not approved",
  "not_approved",
  "not-approved",
  "notapproved",
  "unapproved",
  "rejected",
  "wip",
  "work in progress",
  "in progress",
])
const PART_DETAIL_FIELD_FALLBACK_ALIASES: Record<string, string[]> = {
  description: ["description", "desc", "desc1", "summary_text"],
  revision: ["revision", "rev"],
  category: ["category"],
  material: ["material"],
  finish: ["finish", "treatment", "colour", "color"],
  mass: ["mass", "weight"],
  uom: ["uom", "unit", "unit_of_measure"],
  link: ["link", "oem_internet", "oem_link"],
  oem: ["oem", "manufacturer", "oem_supplier"],
  oem_partnumber: ["oem_partnumber", "oem_part_number", "supplier_partnumber", "supplier_part_number", "mfr_part", "manufacturer_part"],
  datasheet: ["datasheet", "oem_data_sheet", "oem_datasheet", "data_sheet", "datasheet_url"],
  approved: ["approved"],
  approved_by: ["approvedby", "approved_by", "approved"],
  process: [
    "process",
    "processes",
    "process2",
    "process3",
    "secondprocess",
    "thirdprocess",
    "second_process",
    "third_process",
    "second process",
    "third process",
  ],
}

export function normalizeAliasName(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
}

export function readRecordValue(record: Record<string, unknown> | null | undefined, key: string) {
  if (!record) return undefined
  if (Object.prototype.hasOwnProperty.call(record, key)) return record[key]
  const target = normalizeAliasName(key)
  if (!target) return undefined
  for (const [recordKey, value] of Object.entries(record)) {
    if (normalizeAliasName(recordKey) === target) return value
  }
  return undefined
}

export function canonicalFieldAliases(
  config: FieldConfigPayload | null | undefined,
  fieldId: string,
  fallbackAliases: string[],
): string[] {
  const aliases = new Set<string>()
  const add = (value: unknown) => {
    const text = String(value ?? "").trim()
    if (text) aliases.add(text)
  }

  add(fieldId)
  const entry = (config?.canonical_aliases || []).find(
    (item) => normalizeAliasName(item?.field_id) === normalizeAliasName(fieldId),
  )
  for (const alias of entry?.aliases || []) add(alias)
  for (const alias of fallbackAliases) add(alias)

  return Array.from(aliases)
}

export function collectRecordValues(record: Record<string, unknown> | null | undefined, aliases: string[]): unknown[] {
  const values: unknown[] = []
  for (const alias of aliases) {
    const value = readRecordValue(record, alias)
    if (value !== undefined) values.push(value)
  }
  return values
}

export function approvalTextVariants(value: string): string[] {
  const text = String(value || "").trim().toLowerCase()
  if (!text) return []

  const variants = new Set<string>()
  const add = (item: string) => {
    const normalized = item.trim().toLowerCase().replace(/\s+/g, " ")
    if (normalized) variants.add(normalized)
  }

  add(text)
  add(text.replace(/[_-]+/g, " "))

  const alnumSpaced = text.replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ")
  if (alnumSpaced) {
    add(alnumSpaced)
    add(alnumSpaced.replace(/\s+/g, ""))
    add(alnumSpaced.replace(/\s+/g, "_"))
    add(alnumSpaced.replace(/\s+/g, "-"))
  }

  return Array.from(variants)
}

export function explicitApprovalStatus(value: unknown): boolean | null {
  if (value === undefined || value === null) return null
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value !== "string") return null

  const text = value.trim()
  if (!text) return null

  const variants = approvalTextVariants(text)
  if (variants.some((item) => APPROVAL_FALSE_VALUES.has(item))) return false
  if (variants.some((item) => APPROVAL_TRUE_VALUES.has(item))) return true
  return null
}

export function approvalIdentityText(value: unknown): string {
  if (value === undefined || value === null) return ""
  if (Array.isArray(value)) {
    return value
      .map((item) => approvalIdentityText(item))
      .filter(Boolean)
      .join(", ")
      .trim()
  }
  if (explicitApprovalStatus(value) !== null) return ""
  if (typeof value !== "string") return ""
  return value.trim()
}

export function partDetailFieldFallbackAliases(fieldId: string): string[] {
  return PART_DETAIL_FIELD_FALLBACK_ALIASES[fieldId] || [fieldId]
}
