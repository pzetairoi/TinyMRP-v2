/**
 * Which revision a part-detail view should actually use.
 *
 * Extracted so it can be tested: the component keeps a loaded part in state
 * across navigation (React does not unmount it when only a route param
 * changes), so the previously-loaded part must not be allowed to supply the
 * revision for the part now in the URL.
 */
export function effectiveRevisionFor(
  urlPartNumber: string,
  urlRevision: string,
  loaded: { part_number?: string; revision?: string } | null | undefined,
): string {
  const matches =
    (loaded?.part_number ?? "").trim().toLowerCase() === (urlPartNumber ?? "").trim().toLowerCase()
  return ((matches ? loaded?.revision : undefined) ?? urlRevision ?? "").trim()
}
