// frontend/src/pages/BomPage.tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { TreeTable } from 'primereact/treetable'
// PrimeReact's own filter types. A hand-written
// Record<string, { value: any; matchMode: string }> looks equivalent but is
// not: matchMode is a closed union there, so the loose version silently fails
// to typecheck at the call site.
// The two tables on this page need DIFFERENT types - the BOM tree is a
// TreeTable, the where-used list is a DataTable - and they are not
// interchangeable.
import type { TreeTableFilterMeta } from 'primereact/treetable'
import type { TreeNode } from 'primereact/treenode'
import { DataTable } from 'primereact/datatable'
import type { DataTableFilterMeta } from 'primereact/datatable'
import { Column } from 'primereact/column'
import { FilterMatchMode } from 'primereact/api'
import ThumbImg from '../components/ThumbImg'
import FieldSelector from '../components/FieldSelector'
import {
  contextFields,
  defaultFieldIds,
  fieldFilterPlaceholder,
  formatFieldValue,
  loadFieldConfig,
  matchesFieldFilter,
  requiredFieldIds,
  reviewColumnVisible,
  saveFieldPreferences,
  selectedFieldIds,
  updateContextSelection,
  updateReviewColumnVisibility,
  type FieldConfigPayload,
  type FieldDefinition,
  type FieldPreferences,
} from '../lib/fieldConfig'

// Import the ImageStrip component to display images for the part
import ImageStrip from "../components/ImageStrip"
import { findNode, setNodeChildren, withBomOccurrenceKeys } from '../lib/bomTree'
import { apiErrorMessage, apiFetch, isCancelledRequest } from '../lib/api'


// Backend must return Where-Used rows as objects with these keys:
// { parent_pn, parent_desc, qty, uom, alt_group }
// See app/views/whereused.py in the backend patch.

type WURow = {
  parent_pn: string
  parent_desc: string
  qty: number
  uom: string
  alt_group: string
  part_number?: string
  revision?: string
  description?: string
  parent_thumb_urls?: string[]
  [key: string]: any
}

type LazyWUState = {
  first: number
  rows: number
  sortField: string
  sortOrder: 1 | -1
  filters: DataTableFilterMeta
}

const FALLBACK_BOM_FIELDS: FieldDefinition[] = [
  { id: 'thumbnail', label: 'Thumbnail', kind: 'special', filterable: false, sortable: false },
  { id: 'part_number', label: 'Part Number', kind: 'builtin', filterable: true, sortable: true },
  { id: 'revision', label: 'Revision', kind: 'builtin', filterable: true, sortable: true },
  { id: 'description', label: 'Description', kind: 'builtin', filterable: true, sortable: true },
  { id: 'process', label: 'Process', kind: 'builtin', filterable: true, sortable: true },
  { id: 'finish', label: 'Finish', kind: 'builtin', filterable: true, sortable: true },
  { id: 'material', label: 'Material', kind: 'builtin', filterable: true, sortable: true },
  { id: 'approved', label: 'Approved', kind: 'builtin', data_type: 'boolean', filterable: true, sortable: false },
  { id: 'qty', label: 'Qty', kind: 'special', filterable: true, sortable: true },
]

const FALLBACK_WHERE_USED_FIELDS: FieldDefinition[] = [
  { id: 'thumbnail', label: 'Thumbnail', kind: 'special', filterable: false, sortable: false },
  { id: 'part_number', label: 'Part Number', kind: 'builtin', filterable: true, sortable: true },
  { id: 'revision', label: 'Revision', kind: 'builtin', filterable: true, sortable: true },
  { id: 'description', label: 'Description', kind: 'builtin', filterable: true, sortable: true },
  { id: 'approved', label: 'Approved', kind: 'builtin', data_type: 'boolean', filterable: true, sortable: false },
  { id: 'qty', label: 'Qty', kind: 'special', filterable: true, sortable: true },
]

export default function BomPage() {
  // PN comes from router (/ui/bom/:pn). If you are using the Jinja shell, it
  // also exists in window.__INITIAL__.pn; we fall back gracefully.
  const route = useParams()
  const sp = new URLSearchParams(window.location.search)
  const pnQuery = sp.get('pn') || sp.get('q') || ''
  const pn = route.pn || (window as any).__INITIAL__?.pn || pnQuery || ''
  const rev = sp.get('rev') || ((window as any).__INITIAL__?.rev ?? '')

  // --- BOM Tree ---
  const [nodes, setNodes] = useState<TreeNode[]>([])
  const [treeError, setTreeError] = useState<string | null>(null)
  // Large assemblies take seconds to authorise and load. Without this the
  // table looks EMPTY while it works, which reads as "this assembly has no
  // children" - a wrong answer rather than a slow one.
  const [treeLoading, setTreeLoading] = useState(true)
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({})
  const [fieldConfig, setFieldConfig] = useState<FieldConfigPayload | null>(null)
  const [fieldPreferences, setFieldPreferences] = useState<FieldPreferences | null>(null)

  const [treeFilters, setTreeFilters] = useState<TreeTableFilterMeta>({})

  useEffect(() => {
    ;(async () => {
      try {
        const resp = await loadFieldConfig()
        setFieldConfig(resp.config)
        setFieldPreferences(resp.user_preferences || { contexts: {} })
      } catch {}
    })()
  }, [])

  // Load root
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setTreeError(null)
      setTreeLoading(true)
      // Clear immediately: navigating from a child to its parent used to leave
      // the PREVIOUS assembly's rows on screen during the load, which looks
      // like the new part's BOM.
      setNodes([])
      try {
        const root = await apiFetch<TreeNode[]>(`/api/bom_tree?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || '')}`)
        if (!cancelled) setNodes(withBomOccurrenceKeys(root))
      } catch (e) {
        if (!cancelled) {
          setNodes([])
          if (!isCancelledRequest(e)) setTreeError(apiErrorMessage(e, 'Failed to load the BOM tree.'))
        }
      } finally {
        if (!cancelled) setTreeLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn, rev])

  async function loadChildrenFor(key: string) {
    setTreeError(null)
    try {
      const parent = findNode(nodes, key)
      const parentPn = (parent as any)?.data?.pn || key
      const prev = (parent as any)?.data?.rev || ''
      const payload = await apiFetch<TreeNode[]>(`/api/bom_tree?parent=${encodeURIComponent(parentPn)}&parent_rev=${encodeURIComponent(prev)}`)
      const kids: TreeNode[] = withBomOccurrenceKeys(payload, key)
      setNodes((prev) => setNodeChildren(prev, key, kids))
      setExpandedKeys((prev) => ({ ...prev, [key]: true }))
    } catch (e) {
      if (!isCancelledRequest(e)) setTreeError(apiErrorMessage(e, 'Failed to load the selected BOM branch.'))
    }
  }

  // --- Where-Used ---
  const [wuRows, setWuRows] = useState<WURow[]>([])
  const [wuTotal, setWuTotal] = useState(0)
  const [loadingWU, setLoadingWU] = useState(false)
  const [whereUsedError, setWhereUsedError] = useState<string | null>(null)
  const bomFields = fieldConfig ? contextFields(fieldConfig, 'bom_tree') : FALLBACK_BOM_FIELDS
  const whereUsedFields = fieldConfig ? contextFields(fieldConfig, 'where_used') : FALLBACK_WHERE_USED_FIELDS
  const defaultBomIds = fieldConfig ? defaultFieldIds(fieldConfig, 'bom_tree') : FALLBACK_BOM_FIELDS.map((field) => field.id)
  const defaultWhereUsedIds = fieldConfig ? defaultFieldIds(fieldConfig, 'where_used') : FALLBACK_WHERE_USED_FIELDS.map((field) => field.id)
  const requiredBomIds = fieldConfig ? requiredFieldIds(fieldConfig, 'bom_tree') : ['part_number']
  const requiredWhereUsedIds = fieldConfig ? requiredFieldIds(fieldConfig, 'where_used') : ['part_number']
  const selectedBomIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, 'bom_tree') : defaultBomIds
  const selectedWhereUsedIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, 'where_used') : defaultWhereUsedIds
  const showBomReviewColumn = reviewColumnVisible(fieldPreferences, 'bom_tree')

  async function persistFieldSelection(contextName: string, fieldIds: string[]) {
    if (!fieldConfig) return
    const nextPrefs = updateContextSelection(fieldConfig, fieldPreferences, contextName, fieldIds)
    setFieldPreferences(nextPrefs)
    try {
      const resp = await saveFieldPreferences(nextPrefs)
      setFieldPreferences(resp.settings.field_preferences || nextPrefs)
    } catch {}
  }

  async function persistReviewColumnVisibility(visible: boolean) {
    const nextPrefs = updateReviewColumnVisibility(fieldPreferences, 'bom_tree', visible)
    setFieldPreferences(nextPrefs)
    try {
      const resp = await saveFieldPreferences(nextPrefs)
      setFieldPreferences(resp.settings.field_preferences || nextPrefs)
    } catch {}
  }

  function normalizeFilters(next: TreeTableFilterMeta) {
    const out: TreeTableFilterMeta = {}
    for (const [key, value] of Object.entries(next || {})) {
      if (value?.value === '' || value?.value === null || value?.value === undefined) continue
      out[key] = value
    }
    return out
  }

  function clearTreeFilters() {
    setTreeFilters({})
  }

  function reviewFilterMatches(value: unknown, filterValue: unknown) {
    const filter = String(filterValue || '').toLowerCase()
    const severity = String(value || '').toLowerCase()
    if (!filter) return true
    if (filter === 'pending') return Boolean(severity)
    if (filter === 'none') return !severity
    return severity === filter
  }

  function reviewIndicator(node: any) {
    const data = node?.data || node || {}
    if (!data.has_pending_reviews) return <span className="text-muted">—</span>
    const severity = data.pending_review_severity || 'low'
    return (
      <span className={`parts-review-indicator parts-review-indicator--${severity}`} title={`${data.pending_review_count || 0} pending review item(s), ${severity} priority`}>
        <span aria-hidden="true" />
        {data.pending_review_count || 0}
      </span>
    )
  }

  function reviewFilterElement() {
    const value = String(treeFilters.pending_review_severity?.value || '')
    return (
      <select
        className="form-select form-select-sm"
        aria-label="Filter BOM by pending reviews"
        value={value}
        onChange={(e) => setTreeFilters((current) => normalizeFilters({
          ...current,
          pending_review_severity: { value: e.target.value, matchMode: 'custom' },
        }))}
      >
        <option value="">Any</option>
        <option value="pending">Pending</option>
        <option value="high">High</option>
        <option value="normal">Normal</option>
        <option value="low">Low</option>
        <option value="none">None</option>
      </select>
    )
  }

  function booleanFilterElement(options: any) {
    const value = options.value === true ? 'true' : options.value === false ? 'false' : ''
    return (
      <select
        className="form-select form-select-sm"
        aria-label="Filter by final approval status"
        value={value}
        onChange={(event) => {
          const nextValue = event.target.value === '' ? null : event.target.value === 'true'
          options.filterApplyCallback(nextValue)
        }}
      >
        <option value="">Any</option>
        <option value="true">Yes</option>
        <option value="false">No</option>
      </select>
    )
  }

  // PrimeReact's TreeTable rowClassName expects an object of
  // { className: boolean }, not a string. Returning a string happened to work
  // at runtime but was never the documented contract.
  function reviewRowClass(row: any): Record<string, boolean> {
    const data = row?.data || row || {}
    if (!data.has_pending_reviews) return {}
    const severity = data.pending_review_severity || 'low'
    return {
      'parts-review-row': true,
      [`parts-review-row--${severity}`]: true,
    }
  }

  const [lazy, setLazy] = useState<LazyWUState>({
    first: 0,
    rows: 25,
    sortField: 'parent_pn',
    sortOrder: 1,
    filters: {
      parent_pn: { value: '', matchMode: FilterMatchMode.CONTAINS },
      parent_desc: { value: '', matchMode: FilterMatchMode.CONTAINS },
      alt_group: { value: '', matchMode: FilterMatchMode.CONTAINS },
    },
  })

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoadingWU(true)
      setWhereUsedError(null)
      try {
        const j = await apiFetch<{ data?: WURow[]; totalRecords?: number }>('/api/whereused_lazy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pn, rev, ...lazy }),
        })
        if (!cancelled) {
          setWuRows(j.data || [])
          setWuTotal(j.totalRecords || 0)
        }
      } catch (e) {
        // A request killed by navigating away is not a failure to report.
        if (!cancelled && !isCancelledRequest(e)) {
          setWuRows([])
          setWuTotal(0)
          setWhereUsedError(apiErrorMessage(e, 'Failed to load where-used results.'))
        }
      } finally {
        if (!cancelled) setLoadingWU(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn, rev, lazy.first, lazy.rows, lazy.sortField, lazy.sortOrder, JSON.stringify(lazy.filters)])

  function renderBomCell(field: FieldDefinition, node: any) {
    const value = node?.data?.[field.id]
    if (field.id === 'thumbnail') {
      const urls = node?.data?.thumb_urls || []
      const cpn = node?.data?.part_number || node?.data?.pn || ''
      const crev = node?.data?.revision || node?.data?.rev || ''
      return <a href={`/ui/part/${encodeURIComponent(cpn)}?rev=${encodeURIComponent(crev)}`} aria-label={`Open ${cpn} details`}><ThumbImg urls={urls} maxH={32} maxW={48} /></a>
    }
    if (field.id === 'part_number') {
      const cpn = node?.data?.part_number || node?.data?.pn || ''
      const crev = node?.data?.revision || node?.data?.rev || ''
      return <a href={`/ui/part/${encodeURIComponent(cpn)}?rev=${encodeURIComponent(crev)}`}>{cpn}</a>
    }
    return formatFieldValue(value)
  }

  function renderWhereUsedCell(field: FieldDefinition, row: WURow) {
    const value = row?.[field.id]
    const partNumber = row.part_number || row.parent_pn
    const revision = row.revision || ''
    if (field.id === 'thumbnail') return <a href={`/ui/part/${encodeURIComponent(partNumber)}?rev=${encodeURIComponent(revision)}`} aria-label={`Open ${partNumber} details`}><ThumbImg urls={row.parent_thumb_urls || []} maxH={28} maxW={44} /></a>
    if (field.id === 'part_number') return <a href={`/ui/part/${encodeURIComponent(partNumber)}?rev=${encodeURIComponent(revision)}`}>{partNumber}</a>
    return formatFieldValue(value)
  }


  return (
    <div className="p-3">
      <h5 className="mb-2">BOM · {pn}</h5>

      {/* Imágenes del PN (usa última revisión si no se especifica) */}
      <ImageStrip pn={pn} rev={rev || ''} />

{/* BOM TreeTable */}

<div className="mb-4">
  {treeError && <div className="alert alert-danger" role="alert">{treeError}</div>}
  {treeLoading && !treeError && (
    <div className="d-flex align-items-center gap-2 text-muted small mb-2" role="status" aria-live="polite">
      <span className="spinner-border spinner-border-sm" aria-hidden="true" />
      <span>Loading BOM… large assemblies can take a few seconds.</span>
    </div>
  )}
  <div className="d-flex justify-content-end gap-2 mb-2">
    {bomFields.length > 0 && (
      <FieldSelector
        title="BOM fields"
        buttonLabel="Fields"
        availableFields={bomFields}
        selectedIds={selectedBomIds}
        requiredIds={requiredBomIds}
        onChange={(fieldIds) => persistFieldSelection('bom_tree', fieldIds)}
        onReset={() => persistFieldSelection('bom_tree', defaultBomIds)}
        extraOptions={(
          <div className="form-check">
            <input
              className="form-check-input"
              type="checkbox"
              id="bom-reviews-column"
              checked={showBomReviewColumn}
              onChange={(e) => persistReviewColumnVisibility(e.target.checked)}
            />
            <label className="form-check-label small" htmlFor="bom-reviews-column">Reviews</label>
          </div>
        )}
      />
    )}
    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={clearTreeFilters}>
      Clear filters
    </button>
  </div>
  <TreeTable
    value={nodes}
    expandedKeys={expandedKeys}
    onToggle={(e: any) => setExpandedKeys(e.value)}
    onExpand={(e: any) => e?.node?.key && loadChildrenFor(String(e.node.key))}
    filters={treeFilters}
    onFilter={(e: any) => setTreeFilters(normalizeFilters(e.filters || {}))}
    filterDisplay="row"
    scrollable
    scrollHeight="60vh"
    resizableColumns
    columnResizeMode="expand"
    tableStyle={{ tableLayout: 'fixed' }}
    showGridlines
    size="small"
    rowClassName={reviewRowClass}
  >
    {showBomReviewColumn && <Column
      field="pending_review_severity"
      header="Reviews"
      body={reviewIndicator}
      sortable
      filter
      filterMatchMode="custom"
      filterFunction={reviewFilterMatches}
      showFilterMenu={false}
      filterElement={reviewFilterElement()}
      style={{ width: 105 }}
    />}
    {selectedBomIds.map((fieldId) => {
      const field = bomFields.find((item) => item.id === fieldId)
      if (!field) return null
      return (
        <Column
          key={field.id}
          field={field.id}
          filterField={field.id}
          header={field.id === 'thumbnail' ? '' : field.label}
          expander={field.id === 'part_number'}
          sortable={field.sortable !== false}
          filter={field.filterable !== false}
          filterMatchMode="custom"
          filterFunction={(value, filterValue) => matchesFieldFilter(field, value, filterValue)}
          showFilterMenu={false}
          filterPlaceholder={field.data_type === 'boolean' ? undefined : fieldFilterPlaceholder(field)}
          filterElement={field.data_type === 'boolean' ? booleanFilterElement : undefined}
          body={(node: any) => renderBomCell(field, node)}
          style={
            field.id === 'thumbnail'
              ? { width: 70 }
              : field.id === 'part_number'
              ? { width: 240 }
              : field.id === 'qty'
              ? { width: 100 }
              : field.id === 'uom'
              ? { width: 100 }
              : field.id === 'alt_group'
              ? { width: 140 }
              : field.id === 'description'
              ? { minWidth: '28ch', width: '32%' }
              : undefined
          }
        />
      )
    })}
  </TreeTable>
</div>





      {/* Where-used */}
      {whereUsedError && <div className="alert alert-danger" role="alert">{whereUsedError}</div>}
      <DataTable
        value={wuRows}
        header={
          <div className="d-flex align-items-center justify-content-between p-2">
            <div>Where-used</div>
            {whereUsedFields.length > 0 && (
              <FieldSelector
                title="Where-used fields"
                buttonLabel="Fields"
                availableFields={whereUsedFields}
                selectedIds={selectedWhereUsedIds}
                requiredIds={requiredWhereUsedIds}
                onChange={(fieldIds) => persistFieldSelection('where_used', fieldIds)}
                onReset={() => persistFieldSelection('where_used', defaultWhereUsedIds)}
              />
            )}
          </div>
        }
        lazy
        paginator
        totalRecords={wuTotal}
        rows={lazy.rows}
        first={lazy.first}
        loading={loadingWU}
        sortField={lazy.sortField}
        sortOrder={lazy.sortOrder}
        onPage={(e) => setLazy((s) => ({ ...s, first: e.first, rows: e.rows }))}
        onSort={(e) =>
          setLazy((s) => ({
            ...s,
            sortField: (e.sortField as LazyWUState['sortField']) || 'parent_pn',
            sortOrder: (e.sortOrder === -1 ? -1 : 1) as 1 | -1,
          }))
        }
        onFilter={(e) => setLazy((s) => ({ ...s, first: 0, filters: e.filters }))}
        filterDisplay="row"
        removableSort
        rowsPerPageOptions={[10, 25, 50, 100]}
        stripedRows
        responsiveLayout="scroll"
      >
        {selectedWhereUsedIds.map((fieldId) => {
          const field = whereUsedFields.find((item) => item.id === fieldId)
          if (!field) return null
          return (
            <Column
              key={field.id}
              field={field.id}
              header={field.id === 'thumbnail' ? '' : field.label}
              sortable={field.sortable !== false}
              filter={field.filterable !== false}
              showFilterMenu={false}
              filterMatchMode={field.data_type === 'boolean' ? FilterMatchMode.EQUALS : FilterMatchMode.CONTAINS}
              filterMatchModeOptions={field.data_type === 'boolean'
                ? [{ label: 'Equals', value: FilterMatchMode.EQUALS }]
                : [{ label: 'Contains', value: FilterMatchMode.CONTAINS }]}
              filterPlaceholder={field.data_type === 'boolean' ? undefined : fieldFilterPlaceholder(field)}
              filterElement={field.data_type === 'boolean' ? booleanFilterElement : undefined}
              body={(row: WURow) => renderWhereUsedCell(field, row)}
            />
          )
        })}
      </DataTable>
    </div>
  )
}
