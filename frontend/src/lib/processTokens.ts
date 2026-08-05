/**
 * Split a manufacturing-process value into comparable tokens.
 *
 * Process lists come from CAD custom properties, so one part may carry
 * "Milling, Turning", another "milling / turning" and another an array. They
 * have to normalise to the same tokens or process filtering silently misses
 * parts.
 */

export function processTokens(value: unknown): string[] {
  if (value === undefined || value === null) return []
  if (Array.isArray(value)) {
    return value.flatMap((item) => processTokens(item))
  }
  return String(value)
    .split(/\s*(?:,|;|\/|\||&|\+|\r|\n)\s*/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
}
