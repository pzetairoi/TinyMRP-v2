// frontend/src/pages/BomPage.tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { TreeTable } from 'primereact/treetable'
import type { TreeNode } from 'primereact/treenode'
import { DataTable } from 'primereact/datatable'
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
  saveFieldPreferences,
  selectedFieldIds,
  updateContextSelection,
  type FieldConfigPayload,
  type FieldDefinition,
  type FieldPreferences,
} from '../lib/fieldConfig'

// Import the ImageStrip component to display images for the part
import ImageStrip from "../components/ImageStrip"


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
  filters: Record<string, { value: string; matchMode: string }>
}

const FALLBACK_BOM_FIELDS: FieldDefinition[] = [
  { id: 'thumbnail', label: 'Thumbnail', kind: 'special', filterable: false, sortable: false },
  { id: 'part_number', label: 'Part Number', kind: 'builtin', filterable: true, sortable: true },
  { id: 'revision', label: 'Revision', kind: 'builtin', filterable: true, sortable: true },
  { id: 'description', label: 'Description', kind: 'builtin', filterable: true, sortable: true },
  { id: 'process', label: 'Process', kind: 'builtin', filterable: true, sortable: true },
  { id: 'finish', label: 'Finish', kind: 'builtin', filterable: true, sortable: true },
  { id: 'material', label: 'Material', kind: 'builtin', filterable: true, sortable: true },
  { id: 'qty', label: 'Qty', kind: 'special', filterable: true, sortable: true },
]

const FALLBACK_WHERE_USED_FIELDS: FieldDefinition[] = [
  { id: 'thumbnail', label: 'Thumbnail', kind: 'special', filterable: false, sortable: false },
  { id: 'part_number', label: 'Part Number', kind: 'builtin', filterable: true, sortable: true },
  { id: 'revision', label: 'Revision', kind: 'builtin', filterable: true, sortable: true },
  { id: 'description', label: 'Description', kind: 'builtin', filterable: true, sortable: true },
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
  const [expandedKeys, setExpandedKeys] = useState<Record<string, boolean>>({})
  const [fieldConfig, setFieldConfig] = useState<FieldConfigPayload | null>(null)
  const [fieldPreferences, setFieldPreferences] = useState<FieldPreferences | null>(null)

  const [treeFilters, setTreeFilters] = useState<Record<string, { value: any; matchMode: string }>>({})

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
      try {
        const r = await fetch(`/api/bom_tree?pn=${encodeURIComponent(pn)}&rev=${encodeURIComponent(rev || '')}`)
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const root: TreeNode[] = await r.json()
        if (!cancelled) setNodes(root)
      } catch (e) {
        console.error('bom_tree root failed', e)
        if (!cancelled) setNodes([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pn, rev])

  // Helper to immutably set children for a node key
  function setNodeChildren(tree: TreeNode[], key: string, children: TreeNode[]): TreeNode[] {
    return tree.map((n) => {
      if (String(n.key) === String(key)) {
        return { ...n, children }
      }
      if (n.children && n.children.length) {
        return { ...n, children: setNodeChildren(n.children as TreeNode[], key, children) }
      }
      return n
    })
  }

  function findNode(tree: TreeNode[], key: string): TreeNode | undefined {
    for (const n of tree) {
      if (String(n.key) === String(key)) return n
      if (n.children && n.children.length) {
        const hit = findNode(n.children as TreeNode[], key)
        if (hit) return hit
      }
    }
    return undefined
  }

  async function loadChildrenFor(key: string) {
    try {
      const parent = findNode(nodes, key)
      const parentPn = (parent as any)?.data?.pn || key
      const prev = (parent as any)?.data?.rev || ''
      const r = await fetch(`/api/bom_tree?parent=${encodeURIComponent(parentPn)}&parent_rev=${encodeURIComponent(prev)}`)
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const kids: TreeNode[] = await r.json()
      setNodes((prev) => setNodeChildren(prev, key, kids))
      setExpandedKeys((prev) => ({ ...prev, [key]: true }))
    } catch (e) {
      console.error('bom_tree children failed', e)
    }
  }

  // --- Where-Used ---
  const [wuRows, setWuRows] = useState<WURow[]>([])
  const [wuTotal, setWuTotal] = useState(0)
  const [loadingWU, setLoadingWU] = useState(false)
  const bomFields = fieldConfig ? contextFields(fieldConfig, 'bom_tree') : FALLBACK_BOM_FIELDS
  const whereUsedFields = fieldConfig ? contextFields(fieldConfig, 'where_used') : FALLBACK_WHERE_USED_FIELDS
  const defaultBomIds = fieldConfig ? defaultFieldIds(fieldConfig, 'bom_tree') : FALLBACK_BOM_FIELDS.map((field) => field.id)
  const defaultWhereUsedIds = fieldConfig ? defaultFieldIds(fieldConfig, 'where_used') : FALLBACK_WHERE_USED_FIELDS.map((field) => field.id)
  const requiredBomIds = fieldConfig ? requiredFieldIds(fieldConfig, 'bom_tree') : ['part_number']
  const requiredWhereUsedIds = fieldConfig ? requiredFieldIds(fieldConfig, 'where_used') : ['part_number']
  const selectedBomIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, 'bom_tree') : defaultBomIds
  const selectedWhereUsedIds = fieldConfig ? selectedFieldIds(fieldConfig, fieldPreferences, 'where_used') : defaultWhereUsedIds

  async function persistFieldSelection(contextName: string, fieldIds: string[]) {
    if (!fieldConfig) return
    const nextPrefs = updateContextSelection(fieldConfig, fieldPreferences, contextName, fieldIds)
    setFieldPreferences(nextPrefs)
    try {
      const resp = await saveFieldPreferences(nextPrefs)
      setFieldPreferences(resp.settings.field_preferences || nextPrefs)
    } catch {}
  }

  function normalizeFilters(next: Record<string, { value: any; matchMode: string }>) {
    const out: Record<string, { value: any; matchMode: string }> = {}
    for (const [key, value] of Object.entries(next || {})) {
      if (value?.value === '' || value?.value === null || value?.value === undefined) continue
      out[key] = value
    }
    return out
  }

  function clearTreeFilters() {
    setTreeFilters({})
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
      try {
        const r = await fetch('/api/whereused_lazy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pn, rev, ...lazy }),
        })
        if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`)
        const j = await r.json()
        if (!cancelled) {
          setWuRows(j.data || [])
          setWuTotal(j.totalRecords || 0)
        }
      } catch (e) {
        console.error('whereused_lazy failed', e)
        if (!cancelled) {
          setWuRows([])
          setWuTotal(0)
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
      return <ThumbImg urls={urls} maxH={32} maxW={48} />
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
    if (field.id === 'thumbnail') return <ThumbImg urls={row.parent_thumb_urls || []} maxH={28} maxW={44} />
    if (field.id === 'part_number') return formatFieldValue(row.part_number || row.parent_pn)
    return formatFieldValue(value)
  }


  return (
    <div className="p-3">
      <h5 className="mb-2">BOM · {pn}</h5>

      {/* Imágenes del PN (usa última revisión si no se especifica) */}
      <ImageStrip pn={pn} rev={rev || ''} />

{/* BOM TreeTable */}

<div className="mb-4">
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
    showGridlines
    size="small"
  >
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
          filterPlaceholder={fieldFilterPlaceholder(field)}
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
              : undefined
          }
        />
      )
    })}
  </TreeTable>
</div>





      {/* Where-used */}
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
              filterMatchMode="contains"
              filterMatchModeOptions={["contains"]}
              filterPlaceholder={fieldFilterPlaceholder(field)}
              body={(row: WURow) => renderWhereUsedCell(field, row)}
            />
          )
        })}
      </DataTable>
    </div>
  )
}
