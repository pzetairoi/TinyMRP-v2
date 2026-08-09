// Gaps in PrimeReact's own type definitions.
//
// These props WORK at runtime - the BOM tree and the part-detail tree both
// render their filter row in production - but TreeTableProps does not declare
// them. Without this the only options are to delete a working feature or to
// cast the whole props object, which would hide every other type error on the
// same element.
//
// Check on each PrimeReact upgrade: if a declaration lands upstream, delete it
// here rather than keeping two sources of truth.
import 'primereact/treetable'

declare module 'primereact/treetable' {
  interface TreeTableProps {
    /** Renders a filter row under the header. Supported since PrimeReact 8. */
    filterDisplay?: 'row' | 'menu'
    /** Compact row density, same values the DataTable declares. */
    size?: 'small' | 'normal' | 'large'
  }
}
