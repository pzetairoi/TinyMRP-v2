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

/**
 * The revision for the part currently in the URL.
 *
 * `?rev=` with an empty value is MEANINGFUL - it says "this part has no
 * revision" - but an empty string is falsy, so `sp.get("rev") || fallback`
 * silently reached past it. The fallback is __INITIAL__, injected by the
 * server on the FIRST page load and never updated afterwards, so an SPA
 * navigation to a blank-revision part inherited the revision of whatever page
 * the browser happened to load first.
 *
 * The visible result was a page whose address bar was right while every
 * request it made carried the wrong revision and 404'd, and which came good
 * after F5 because that regenerates __INITIAL__.
 *
 * So: if the parameter is PRESENT, use it, empty or not. Fall back only when
 * it is absent, and only when the server's initial state describes the same
 * part we are looking at.
 */
export function revisionFromLocation(
  search: string,
  urlPartNumber: string,
  initial: { pn?: string; rev?: string } | null | undefined,
): string {
  const params = new URLSearchParams(search || '')
  const fromUrl = params.get('rev')
  if (fromUrl !== null) return fromUrl

  const initialPn = (initial?.pn ?? '').trim().toLowerCase()
  if (initialPn && initialPn === (urlPartNumber ?? '').trim().toLowerCase()) {
    return initial?.rev ?? ''
  }
  return ''
}
