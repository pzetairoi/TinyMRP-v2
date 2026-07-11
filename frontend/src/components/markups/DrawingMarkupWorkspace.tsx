// frontend/src/components/markups/DrawingMarkupWorkspace.tsx
// Fabric.js overlay editor for the exported drawing PNG. The PNG/PDF are never
// modified: the image is a plain <img> under a transparent Fabric canvas and
// only the vector layer is persisted (as JSON) through the markup API.
import { useEffect, useRef, useState } from 'react'
import { ActiveSelection, Canvas, Ellipse, Line, PencilBrush, Rect, Textbox } from 'fabric'
import MarkupToolbar from './MarkupToolbar'
import MarkupThreadsPanel from './MarkupThreadsPanel'
import {
  TM_OBJECT_ID,
  ensureObjectIds,
  makeArrow,
  makeCloudPath,
  newObjectId,
  serializeCanvas,
} from './fabricHelpers'
import type {
  DrawingImageRow,
  MarkupCanvasJson,
  MarkupDraft,
  MarkupLayer,
  MarkupSaveState,
  MarkupThread,
  MarkupThreadPriority,
  MarkupTool,
} from './types'

type Props = {
  pn: string
  rev: string
  pdfHref: string
  drawingSource: DrawingImageRow | null
  layer: MarkupLayer | null
  layerLoading: boolean
  layerError: string | null
  canEdit: boolean
  onLayerChange: (layer: MarkupLayer) => void
  draftRef: React.MutableRefObject<MarkupDraft | null>
  focusThreadId?: string | null
  onFocusHandled?: () => void
}

const DRAW_TOOLS: MarkupTool[] = ['arrow', 'rect', 'ellipse', 'cloud']

function clientXY(e: any): { x: number; y: number } {
  if (e && e.touches && e.touches.length) return { x: e.touches[0].clientX, y: e.touches[0].clientY }
  return { x: e?.clientX ?? 0, y: e?.clientY ?? 0 }
}

export default function DrawingMarkupWorkspace({
  pn,
  rev,
  pdfHref,
  drawingSource,
  layer,
  layerLoading,
  layerError,
  canEdit,
  onLayerChange,
  draftRef,
  focusThreadId,
  onFocusHandled,
}: Props) {
  const stageRef = useRef<HTMLDivElement | null>(null)
  const canvasElRef = useRef<HTMLCanvasElement | null>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const fabricRef = useRef<Canvas | null>(null)

  const [imgIdx, setImgIdx] = useState(0)
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null)
  const [wrapSize, setWrapSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 })
  const [fabricReady, setFabricReady] = useState(false)
  const [canvasLoaded, setCanvasLoaded] = useState(false)

  const [tool, setTool] = useState<MarkupTool>(canEdit ? 'select' : 'pan')
  const [strokeColor, setStrokeColor] = useState('#d00000')
  const [strokeWidth, setStrokeWidth] = useState(2)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [saveState, setSaveState] = useState<MarkupSaveState>('saved')
  const [canUndo, setCanUndo] = useState(false)
  const [canRedo, setCanRedo] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [threadBusy, setThreadBusy] = useState(false)
  const [threadError, setThreadError] = useState<string | null>(null)

  // Refs mirroring state for use inside Fabric event handlers.
  const toolRef = useRef(tool)
  const strokeColorRef = useRef(strokeColor)
  const strokeWidthRef = useRef(strokeWidth)
  const canEditRef = useRef(canEdit)
  const layerRef = useRef(layer)
  const saveStateRef = useRef(saveState)
  toolRef.current = tool
  strokeColorRef.current = strokeColor
  strokeWidthRef.current = strokeWidth
  canEditRef.current = canEdit
  layerRef.current = layer
  saveStateRef.current = saveState

  // View state (logical scene coords == natural image pixels).
  const baseScaleRef = useRef(1)
  const userZoomRef = useRef(1)
  const panRef = useRef({ x: 0, y: 0 })

  // Editing state.
  const baseVersionRef = useRef(0)
  const fingerprintRef = useRef('')
  const savedJsonRef = useRef<string | null>(null)
  const historyRef = useRef<string[]>([])
  const historyIndexRef = useRef(-1)
  const suspendRef = useRef(false)
  const initialLoadedRef = useRef(false)
  const drawStateRef = useRef<null | { kind: MarkupTool; startX: number; startY: number; obj?: any }>(null)
  const panStateRef = useRef<null | { startX: number; startY: number; panX: number; panY: number }>(null)
  const highlightTimerRef = useRef<number | null>(null)

  const sourceFileId = drawingSource?.source_file_id || ''
  const imgUrls = drawingSource?.urls || []
  const imgUrl = imgUrls.length && imgIdx < imgUrls.length ? imgUrls[imgIdx] : ''

  // ------------------------------------------------------------------
  // View helpers
  // ------------------------------------------------------------------
  function applyView() {
    const canvas = fabricRef.current
    const z = baseScaleRef.current * userZoomRef.current
    const { x, y } = panRef.current
    if (canvas) canvas.setViewportTransform([z, 0, 0, z, x, y])
    if (imgRef.current) imgRef.current.style.transform = `matrix(${z},0,0,${z},${x},${y})`
  }

  function zoomBy(factor: number) {
    const canvas = fabricRef.current
    if (!canvas) return
    const next = Math.min(8, Math.max(0.4, userZoomRef.current * factor))
    if (next === userZoomRef.current) return
    const zOld = baseScaleRef.current * userZoomRef.current
    const zNew = baseScaleRef.current * next
    const cx = canvas.getWidth() / 2
    const cy = canvas.getHeight() / 2
    panRef.current = {
      x: cx - ((cx - panRef.current.x) * zNew) / zOld,
      y: cy - ((cy - panRef.current.y) * zNew) / zOld,
    }
    userZoomRef.current = next
    applyView()
  }

  function fitView() {
    userZoomRef.current = 1
    panRef.current = { x: 0, y: 0 }
    applyView()
  }

  /** Stroke/font sizes are chosen in display pixels; convert to logical
   * (natural-image) pixels at the current zoom so drawing feels WYSIWYG. */
  function logicalSize(displayPx: number): number {
    const z = baseScaleRef.current * userZoomRef.current
    return z > 0 ? displayPx / z : displayPx
  }

  // ------------------------------------------------------------------
  // History / dirty state
  // ------------------------------------------------------------------
  function refreshDirty() {
    if (saveStateRef.current === 'conflict' || saveStateRef.current === 'saving') return
    const canvas = fabricRef.current
    if (!canvas) return
    if (savedJsonRef.current === null) {
      setSaveState('dirty')
      return
    }
    const current = JSON.stringify(serializeCanvas(canvas))
    setSaveState(current === savedJsonRef.current ? 'saved' : 'dirty')
  }

  function updateDraft() {
    const canvas = fabricRef.current
    if (!canvas || !sourceFileId) return
    if (saveStateRef.current === 'dirty') {
      draftRef.current = {
        sourceFileId,
        fingerprint: fingerprintRef.current,
        baseVersion: baseVersionRef.current,
        canvasJson: serializeCanvas(canvas),
        dirty: true,
      }
    }
  }

  function snapshotHistory() {
    const canvas = fabricRef.current
    if (!canvas) return
    const json = JSON.stringify(serializeCanvas(canvas))
    const stack = historyRef.current.slice(0, historyIndexRef.current + 1)
    if (stack.length && stack[stack.length - 1] === json) return
    stack.push(json)
    while (stack.length > 60) stack.shift()
    historyRef.current = stack
    historyIndexRef.current = stack.length - 1
    setCanUndo(historyIndexRef.current > 0)
    setCanRedo(false)
  }

  function onCanvasMutated(target?: any) {
    if (suspendRef.current) return
    if (target && (target.__tmTemp || target.excludeFromExport)) return
    snapshotHistory()
    refreshDirty()
    updateDraft()
  }

  async function loadCanvasJson(json: MarkupCanvasJson) {
    const canvas = fabricRef.current
    if (!canvas) return
    suspendRef.current = true
    try {
      await canvas.loadFromJSON({ version: json.version, objects: json.objects || [] })
      ensureObjectIds(canvas, json)
      canvas.discardActiveObject()
      canvas.requestRenderAll()
    } finally {
      suspendRef.current = false
    }
    applyView()
  }

  async function applyHistory(index: number) {
    const stack = historyRef.current
    if (index < 0 || index >= stack.length) return
    historyIndexRef.current = index
    await loadCanvasJson(JSON.parse(stack[index]) as MarkupCanvasJson)
    setCanUndo(index > 0)
    setCanRedo(index < stack.length - 1)
    setSelectedIds([])
    refreshDirty()
    updateDraft()
  }

  // ------------------------------------------------------------------
  // API calls
  // ------------------------------------------------------------------
  function apiBody(extra: Record<string, any>) {
    return JSON.stringify({
      rev,
      source_file_id: sourceFileId,
      source_fingerprint: fingerprintRef.current,
      page_number: 1,
      ...extra,
    })
  }

  async function fetchLayerFresh(): Promise<MarkupLayer | null> {
    try {
      const qs = new URLSearchParams({ rev, source_file_id: sourceFileId })
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/drawing-markups?${qs.toString()}`)
      const j = await resp.json().catch(() => null)
      if (!resp.ok || !j?.ok) throw new Error(j?.message || `HTTP ${resp.status}`)
      return j as MarkupLayer
    } catch (e: any) {
      setActionError(e?.message || 'Failed to load markup layer')
      return null
    }
  }

  async function save(): Promise<boolean> {
    const canvas = fabricRef.current
    if (!canvas || !canEditRef.current || !sourceFileId) return false
    setActionError(null)
    setSaveState('saving')
    const canvasJson = serializeCanvas(canvas)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/drawing-markups`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: apiBody({ expected_version: baseVersionRef.current, canvas_json: canvasJson }),
      })
      const j = await resp.json().catch(() => null)
      if (resp.status === 409) {
        setSaveState('conflict')
        setActionError(j?.message || 'The markup layer changed on the server. Reload before saving.')
        return false
      }
      if (!resp.ok || !j?.ok) throw new Error(j?.message || `HTTP ${resp.status}`)
      baseVersionRef.current = Number(j.version || 0)
      fingerprintRef.current = j.source?.fingerprint || fingerprintRef.current
      savedJsonRef.current = JSON.stringify(canvasJson)
      draftRef.current = null
      setSaveState('saved')
      onLayerChange(j as MarkupLayer)
      return true
    } catch (e: any) {
      setSaveState('dirty')
      setActionError(e?.message || 'Failed to save markups')
      return false
    }
  }

  async function reloadFromServer() {
    setActionError(null)
    const fresh = await fetchLayerFresh()
    const canvas = fabricRef.current
    if (!fresh || !canvas) return
    baseVersionRef.current = Number(fresh.version || 0)
    fingerprintRef.current = fresh.source?.fingerprint || ''
    await loadCanvasJson(fresh.canvas_json || { objects: [] })
    savedJsonRef.current = JSON.stringify(serializeCanvas(canvas))
    historyRef.current = [savedJsonRef.current]
    historyIndexRef.current = 0
    setCanUndo(false)
    setCanRedo(false)
    setSelectedIds([])
    draftRef.current = null
    setSaveState('saved')
    onLayerChange(fresh)
  }

  async function threadRequest(path: string, method: string, extra: Record<string, any>): Promise<boolean> {
    if (!sourceFileId) return false
    setThreadBusy(true)
    setThreadError(null)
    try {
      const resp = await fetch(`/api/parts/${encodeURIComponent(pn)}/drawing-markups${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: apiBody(extra),
      })
      const j = await resp.json().catch(() => null)
      if (resp.status === 409) {
        setSaveState('conflict')
        setThreadError(j?.message || 'The drawing or markup layer changed. Reload required.')
        return false
      }
      if (!resp.ok || !j?.ok) throw new Error(j?.message || `HTTP ${resp.status}`)
      // Thread mutations bump the layer version server-side.
      baseVersionRef.current = Number(j.version || baseVersionRef.current)
      onLayerChange(j as MarkupLayer)
      return true
    } catch (e: any) {
      setThreadError(e?.message || 'Request failed')
      return false
    } finally {
      setThreadBusy(false)
    }
  }

  async function createThread(input: {
    object_ids: string[]
    title: string
    priority: MarkupThreadPriority
    message: string
  }): Promise<boolean> {
    // Threads link to persisted objects: save the canvas first when dirty.
    if (saveStateRef.current === 'dirty') {
      const ok = await save()
      if (!ok) {
        setThreadError('Save the markup changes before adding a review comment.')
        return false
      }
    }
    return threadRequest('/threads', 'POST', {
      object_ids: input.object_ids,
      title: input.title,
      priority: input.priority,
      message: input.message,
    })
  }

  // ------------------------------------------------------------------
  // Selection / focus / delete
  // ------------------------------------------------------------------
  function updateSelection() {
    const canvas = fabricRef.current
    if (!canvas) {
      setSelectedIds([])
      return
    }
    const ids = canvas
      .getActiveObjects()
      .map((o: any) => o[TM_OBJECT_ID])
      .filter((v: any) => typeof v === 'string' && v)
    setSelectedIds(ids)
  }

  function deleteSelected() {
    const canvas = fabricRef.current
    if (!canvas || !canEditRef.current || saveStateRef.current === 'conflict') return
    const objs = canvas.getActiveObjects().filter((o: any) => !o.excludeFromExport && !o.__tmTemp)
    if (!objs.length) return
    const ids = objs.map((o: any) => o[TM_OBJECT_ID]).filter(Boolean)
    const linkedOpen = (layerRef.current?.threads || []).filter(
      (t) => t.status === 'open' && t.object_ids.some((id) => ids.includes(id)),
    )
    if (linkedOpen.length) {
      const ok = window.confirm(
        `${linkedOpen.length} open review thread(s) reference the selected markup. ` +
          'Deleting will unlink them; the discussion history is kept. Continue?',
      )
      if (!ok) return
    }
    suspendRef.current = true
    canvas.discardActiveObject()
    objs.forEach((o) => canvas.remove(o))
    suspendRef.current = false
    canvas.requestRenderAll()
    setSelectedIds([])
    snapshotHistory()
    refreshDirty()
    updateDraft()
  }

  function focusThread(thread: MarkupThread) {
    const canvas = fabricRef.current
    if (!canvas) return
    const objs = canvas.getObjects().filter((o: any) => thread.object_ids.includes(o[TM_OBJECT_ID]))
    if (!objs.length) {
      setThreadError('Markup no longer present on the drawing.')
      return
    }
    canvas.discardActiveObject()
    if (canEditRef.current) {
      if (objs.length === 1) canvas.setActiveObject(objs[0])
      else canvas.setActiveObject(new ActiveSelection(objs, { canvas }))
    }

    // Scene-space bounding box across all linked objects.
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    objs.forEach((o: any) => {
      const coords = typeof o.getCoords === 'function' ? o.getCoords() : []
      coords.forEach((p: any) => {
        minX = Math.min(minX, p.x)
        minY = Math.min(minY, p.y)
        maxX = Math.max(maxX, p.x)
        maxY = Math.max(maxY, p.y)
      })
    })
    if (!isFinite(minX)) return

    // Bring the bbox centre into the middle of the viewport at current zoom;
    // zoom in a little when the target is tiny on screen.
    const bw = Math.max(1, maxX - minX)
    const bh = Math.max(1, maxY - minY)
    let z = baseScaleRef.current * userZoomRef.current
    if (Math.max(bw, bh) * z < 60) {
      const target = Math.min(8, Math.max(userZoomRef.current, 160 / (Math.max(bw, bh) * baseScaleRef.current)))
      userZoomRef.current = Math.min(8, target)
      z = baseScaleRef.current * userZoomRef.current
    }
    const cx = canvas.getWidth() / 2
    const cy = canvas.getHeight() / 2
    panRef.current = { x: cx - z * (minX + bw / 2), y: cy - z * (minY + bh / 2) }
    applyView()

    // Transient highlight; excludeFromExport keeps it out of history/saves
    // and out of the persisted stored style.
    const pad = Math.max(8, logicalSize(10))
    const highlight = new Rect({
      left: minX - pad,
      top: minY - pad,
      originX: 'left',
      originY: 'top',
      width: bw + pad * 2,
      height: bh + pad * 2,
      fill: 'rgba(255,193,7,0.18)',
      stroke: '#ff9800',
      strokeWidth: logicalSize(2),
      strokeDashArray: [logicalSize(6), logicalSize(4)],
      selectable: false,
      evented: false,
      excludeFromExport: true,
    })
    ;(highlight as any).__tmTemp = true
    suspendRef.current = true
    canvas.add(highlight)
    suspendRef.current = false
    canvas.requestRenderAll()
    if (highlightTimerRef.current) window.clearTimeout(highlightTimerRef.current)
    highlightTimerRef.current = window.setTimeout(() => {
      const c = fabricRef.current
      if (!c) return
      suspendRef.current = true
      try {
        c.remove(highlight)
        c.requestRenderAll()
      } finally {
        suspendRef.current = false
      }
    }, 1800)
    updateSelection()
  }

  // ------------------------------------------------------------------
  // Tool configuration + pointer handlers
  // ------------------------------------------------------------------
  function configureTool(canvas: Canvas, nextTool: MarkupTool) {
    const editable = canEditRef.current && saveStateRef.current !== 'conflict'
    canvas.isDrawingMode = editable && nextTool === 'freehand'
    if (canvas.isDrawingMode) {
      if (!canvas.freeDrawingBrush) canvas.freeDrawingBrush = new PencilBrush(canvas)
      const brush = canvas.freeDrawingBrush as PencilBrush
      brush.color = strokeColorRef.current
      brush.width = Math.max(0.5, logicalSize(strokeWidthRef.current))
    }
    canvas.selection = editable && nextTool === 'select'
    canvas.skipTargetFind = !(editable && nextTool === 'select')
    canvas.defaultCursor = nextTool === 'pan' ? 'grab' : nextTool === 'select' ? 'default' : 'crosshair'
    if (nextTool !== 'select') {
      canvas.discardActiveObject()
      canvas.requestRenderAll()
    }
  }

  function handleMouseDown(canvas: Canvas, opt: any) {
    const t = toolRef.current
    if (t === 'pan') {
      const c = clientXY(opt.e)
      panStateRef.current = { startX: c.x, startY: c.y, panX: panRef.current.x, panY: panRef.current.y }
      canvas.defaultCursor = 'grabbing'
      return
    }
    if (!canEditRef.current || saveStateRef.current === 'conflict') return
    if (t === 'select' || t === 'freehand') return

    const p = canvas.getScenePoint(opt.e)
    if (t === 'text') {
      const fontSize = Math.max(6, logicalSize(18))
      const tb = new Textbox('Text', {
        left: p.x,
        top: p.y,
        originX: 'left',
        originY: 'top',
        width: Math.max(60, logicalSize(140)),
        fontSize,
        fill: strokeColorRef.current,
        fontFamily: 'Helvetica, Arial, sans-serif',
      })
      canvas.add(tb)
      setTool('select')
      canvas.setActiveObject(tb)
      tb.enterEditing()
      tb.selectAll()
      canvas.requestRenderAll()
      return
    }

    if (!DRAW_TOOLS.includes(t)) return
    const stroke = strokeColorRef.current
    const width = Math.max(0.5, logicalSize(strokeWidthRef.current))
    let obj: any = null
    if (t === 'rect') {
      obj = new Rect({ left: p.x, top: p.y, originX: 'left', originY: 'top', width: 1, height: 1, fill: '', stroke, strokeWidth: width })
    } else if (t === 'ellipse') {
      obj = new Ellipse({ left: p.x, top: p.y, originX: 'left', originY: 'top', rx: 1, ry: 1, fill: '', stroke, strokeWidth: width })
    } else if (t === 'arrow') {
      obj = new Line([p.x, p.y, p.x, p.y], { stroke, strokeWidth: width, strokeLineCap: 'round', selectable: false, evented: false })
    } else if (t === 'cloud') {
      obj = new Rect({
        left: p.x,
        top: p.y,
        originX: 'left',
        originY: 'top',
        width: 1,
        height: 1,
        fill: '',
        stroke,
        strokeWidth: Math.max(0.5, width / 2),
        strokeDashArray: [logicalSize(5), logicalSize(4)],
      })
    }
    if (!obj) return
    obj.__tmTemp = true
    obj.selectable = false
    obj.evented = false
    canvas.add(obj)
    drawStateRef.current = { kind: t, startX: p.x, startY: p.y, obj }
  }

  function handleMouseMove(canvas: Canvas, opt: any) {
    if (panStateRef.current) {
      const c = clientXY(opt.e)
      panRef.current = {
        x: panStateRef.current.panX + (c.x - panStateRef.current.startX),
        y: panStateRef.current.panY + (c.y - panStateRef.current.startY),
      }
      applyView()
      return
    }
    const draw = drawStateRef.current
    if (!draw || !draw.obj) return
    const p = canvas.getScenePoint(opt.e)
    const left = Math.min(draw.startX, p.x)
    const top = Math.min(draw.startY, p.y)
    const w = Math.abs(p.x - draw.startX)
    const h = Math.abs(p.y - draw.startY)
    if (draw.kind === 'rect' || draw.kind === 'cloud') {
      draw.obj.set({ left, top, width: Math.max(1, w), height: Math.max(1, h) })
    } else if (draw.kind === 'ellipse') {
      draw.obj.set({ left, top, rx: Math.max(1, w / 2), ry: Math.max(1, h / 2) })
    } else if (draw.kind === 'arrow') {
      draw.obj.set({ x2: p.x, y2: p.y })
    }
    draw.obj.setCoords()
    canvas.requestRenderAll()
  }

  function handleMouseUp(canvas: Canvas, opt: any) {
    if (panStateRef.current) {
      panStateRef.current = null
      canvas.defaultCursor = toolRef.current === 'pan' ? 'grab' : 'default'
      return
    }
    const draw = drawStateRef.current
    drawStateRef.current = null
    if (!draw || !draw.obj) return
    const p = canvas.getScenePoint(opt.e)
    const dx = Math.abs(p.x - draw.startX)
    const dy = Math.abs(p.y - draw.startY)
    const minDrag = logicalSize(4)

    const discardTemp = () => {
      suspendRef.current = true
      canvas.remove(draw.obj)
      suspendRef.current = false
      canvas.requestRenderAll()
    }

    if (dx < minDrag && dy < minDrag) {
      discardTemp()
      return
    }

    const stroke = strokeColorRef.current
    const width = Math.max(0.5, logicalSize(strokeWidthRef.current))

    if (draw.kind === 'rect' || draw.kind === 'ellipse') {
      const obj = draw.obj
      obj.__tmTemp = false
      obj.selectable = true
      obj.evented = true
      if (!obj[TM_OBJECT_ID]) obj[TM_OBJECT_ID] = newObjectId()
      obj.setCoords()
      snapshotHistory()
      refreshDirty()
      updateDraft()
    } else if (draw.kind === 'arrow') {
      discardTemp()
      const arrow = makeArrow(draw.startX, draw.startY, p.x, p.y, { stroke, strokeWidth: width })
      ;(arrow as any)[TM_OBJECT_ID] = newObjectId()
      canvas.add(arrow)
    } else if (draw.kind === 'cloud') {
      discardTemp()
      const left = Math.min(draw.startX, p.x)
      const top = Math.min(draw.startY, p.y)
      const cloud = makeCloudPath(left, top, dx, dy, { stroke, strokeWidth: width })
      ;(cloud as any)[TM_OBJECT_ID] = newObjectId()
      canvas.add(cloud)
    }
    canvas.requestRenderAll()
    // One shape per activation; return to Select (freehand stays active).
    setTool('select')
  }

  // ------------------------------------------------------------------
  // Fabric lifecycle
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!natural || !canvasElRef.current || fabricRef.current) return
    const canvas = new Canvas(canvasElRef.current, {
      selection: true,
      preserveObjectStacking: true,
    })
    fabricRef.current = canvas

    canvas.on('object:added', (e: any) => {
      const t: any = e.target
      if (t && !t.__tmTemp && !t.excludeFromExport && !t[TM_OBJECT_ID]) t[TM_OBJECT_ID] = newObjectId()
      onCanvasMutated(t)
    })
    canvas.on('object:modified', (e: any) => onCanvasMutated(e.target))
    canvas.on('object:removed', (e: any) => onCanvasMutated(e.target))
    canvas.on('text:editing:exited', (e: any) => onCanvasMutated(e.target))
    canvas.on('selection:created', updateSelection)
    canvas.on('selection:updated', updateSelection)
    canvas.on('selection:cleared', () => setSelectedIds([]))
    canvas.on('mouse:down', (opt: any) => handleMouseDown(canvas, opt))
    canvas.on('mouse:move', (opt: any) => handleMouseMove(canvas, opt))
    canvas.on('mouse:up', (opt: any) => handleMouseUp(canvas, opt))

    configureTool(canvas, toolRef.current)
    setFabricReady(true)

    return () => {
      // Preserve unsaved edits across tab switches; the parent keeps the draft.
      try {
        if (saveStateRef.current === 'dirty') {
          draftRef.current = {
            sourceFileId,
            fingerprint: fingerprintRef.current,
            baseVersion: baseVersionRef.current,
            canvasJson: serializeCanvas(canvas),
            dirty: true,
          }
        } else if (saveStateRef.current === 'saved') {
          draftRef.current = null
        }
      } catch { /* draft is best-effort */ }
      if (highlightTimerRef.current) window.clearTimeout(highlightTimerRef.current)
      canvas.dispose()
      fabricRef.current = null
      setFabricReady(false)
    }
  }, [natural])

  // Initial content load: draft (unsaved work) wins over the saved layer.
  useEffect(() => {
    if (!fabricReady || !layer || initialLoadedRef.current) return
    initialLoadedRef.current = true
    const canvas = fabricRef.current
    if (!canvas) return
    ;(async () => {
      fingerprintRef.current = layer.source?.fingerprint || ''
      const draft = draftRef.current
      const draftUsable =
        !!draft &&
        draft.dirty &&
        draft.sourceFileId === sourceFileId &&
        draft.fingerprint === fingerprintRef.current
      if (draftUsable && draft) {
        baseVersionRef.current = draft.baseVersion
        await loadCanvasJson(draft.canvasJson)
        savedJsonRef.current = null // unknown saved baseline until next save/reload
        setSaveState('dirty')
      } else {
        baseVersionRef.current = Number(layer.version || 0)
        await loadCanvasJson(layer.canvas_json || { objects: [] })
        savedJsonRef.current = JSON.stringify(serializeCanvas(canvas))
        setSaveState('saved')
      }
      historyRef.current = [JSON.stringify(serializeCanvas(canvas))]
      historyIndexRef.current = 0
      setCanUndo(false)
      setCanRedo(false)
      setCanvasLoaded(true)
    })()
  }, [fabricReady, layer])

  // Stage sizing: the wrapper matches the fitted image rectangle exactly, so
  // the overlay always aligns with the rendered drawing (no letterbox skew).
  useEffect(() => {
    if (!natural) return
    const stage = stageRef.current
    if (!stage) return
    const compute = () => {
      const cw = stage.clientWidth
      const ch = stage.clientHeight
      if (!cw || !ch) return
      const fit = Math.min(cw / natural.w, ch / natural.h)
      const fitW = Math.max(1, Math.floor(natural.w * fit))
      const fitH = Math.max(1, Math.floor(natural.h * fit))
      setWrapSize((prev) => (prev.w === fitW && prev.h === fitH ? prev : { w: fitW, h: fitH }))
      const oldBase = baseScaleRef.current
      baseScaleRef.current = fitW / natural.w
      if (oldBase > 0 && oldBase !== baseScaleRef.current) {
        const ratio = baseScaleRef.current / oldBase
        panRef.current = { x: panRef.current.x * ratio, y: panRef.current.y * ratio }
      }
      const canvas = fabricRef.current
      if (canvas) canvas.setDimensions({ width: fitW, height: fitH })
      applyView()
    }
    compute()
    const ro = new ResizeObserver(() => compute())
    ro.observe(stage)
    return () => ro.disconnect()
  }, [natural])

  // Tool/permission changes.
  useEffect(() => {
    const canvas = fabricRef.current
    if (canvas) configureTool(canvas, tool)
  }, [tool, canEdit, saveState === 'conflict', fabricReady])

  // Keyboard delete (never while typing in inputs or editing a textbox).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== 'Delete' && e.key !== 'Backspace') return
      const el = e.target as HTMLElement | null
      if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)) return
      const canvas = fabricRef.current
      if (!canvas) return
      const active: any = canvas.getActiveObject()
      if (active && active.isEditing) return
      if (!canvas.getActiveObjects().length) return
      e.preventDefault()
      deleteSelected()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // "View on drawing" navigation coming from the Notes & Comments tab.
  useEffect(() => {
    if (!focusThreadId || !canvasLoaded) return
    const thread = (layerRef.current?.threads || []).find((t) => t.id === focusThreadId)
    if (thread) {
      if (thread.linked) focusThread(thread)
      else setThreadError('Markup no longer present on the drawing.')
    }
    onFocusHandled?.()
  }, [focusThreadId, canvasLoaded])

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  const missingDrawingPng = !drawingSource
  const showEditor = !missingDrawingPng

  return (
    <div className="pd-markup-root">
      {showEditor ? (
        <MarkupToolbar
          tool={tool}
          onToolChange={setTool}
          strokeColor={strokeColor}
          onStrokeColorChange={setStrokeColor}
          strokeWidth={strokeWidth}
          onStrokeWidthChange={setStrokeWidth}
          canEdit={canEdit && (layer ? layer.can_edit : true)}
          hasSelection={selectedIds.length > 0}
          canUndo={canUndo}
          canRedo={canRedo}
          saveState={saveState}
          onDelete={deleteSelected}
          onUndo={() => applyHistory(historyIndexRef.current - 1)}
          onRedo={() => applyHistory(historyIndexRef.current + 1)}
          onZoomIn={() => zoomBy(1.25)}
          onZoomOut={() => zoomBy(1 / 1.25)}
          onFitView={fitView}
          onSave={save}
          onReload={reloadFromServer}
          pdfHref={pdfHref}
        />
      ) : null}

      {layer && layer.stale_layers_count > 0 ? (
        <div className="alert alert-info py-1 px-2 small mb-2 pd-markup-stale">
          <i className="pi pi-history me-1" aria-hidden="true" />
          The drawing file changed since earlier markups were made. {layer.stale_layers_count} older markup layer
          {layer.stale_layers_count > 1 ? 's are' : ' is'} kept as history for previous drawing content.
        </div>
      ) : null}
      {actionError ? <div className="alert alert-danger py-1 px-2 small mb-2">{actionError}</div> : null}
      {layerError ? <div className="alert alert-warning py-1 px-2 small mb-2">{layerError}</div> : null}

      <div className="pd-markup-body">
        <div className="pd-markup-stage" ref={stageRef}>
          {missingDrawingPng ? (
            <div className="pd-markup-missing">
              <i className="pi pi-image" aria-hidden="true" />
              <div className="fw-semibold">No drawing PNG available for web markup</div>
              <div className="text-muted small">
                Generate/refresh the exported drawing PNG for this part to enable drawing markups. The original PDF
                remains available below.
              </div>
              {pdfHref ? (
                <a className="btn btn-sm btn-success" href={pdfHref} target="_blank" rel="noreferrer" title="Open PDF drawing">
                  <i className="pi pi-file-pdf me-1" aria-hidden="true" />
                  Open PDF
                </a>
              ) : null}
            </div>
          ) : (
            <>
              <div
                className="pd-markup-canvas-wrap"
                style={{ width: wrapSize.w || undefined, height: wrapSize.h || undefined }}
              >
                {imgUrl ? (
                  <img
                    ref={imgRef}
                    src={imgUrl}
                    alt={`Drawing for ${pn}${rev ? ` rev ${rev}` : ''}`}
                    className="pd-markup-image"
                    draggable={false}
                    style={natural ? { width: natural.w, height: natural.h } : undefined}
                    onLoad={(e) => {
                      const el = e.currentTarget
                      if (el.naturalWidth && el.naturalHeight) {
                        setNatural((prev) =>
                          prev && prev.w === el.naturalWidth && prev.h === el.naturalHeight
                            ? prev
                            : { w: el.naturalWidth, h: el.naturalHeight },
                        )
                      }
                    }}
                    onError={() => {
                      if (imgIdx < imgUrls.length - 1) setImgIdx(imgIdx + 1)
                    }}
                  />
                ) : (
                  <div className="text-muted small p-3">Drawing image unavailable.</div>
                )}
                {natural ? <canvas ref={canvasElRef} /> : null}
              </div>
              {layerLoading ? <div className="pd-markup-loading small text-muted">Loading markups...</div> : null}
            </>
          )}
        </div>

        <MarkupThreadsPanel
          threads={layer?.threads || []}
          canEdit={canEdit && !!layer?.can_edit && !missingDrawingPng}
          selectedObjectIds={selectedIds}
          busy={threadBusy}
          loading={layerLoading && !layer}
          error={threadError}
          onCreateThread={createThread}
          onReply={(threadId, text) => threadRequest(`/threads/${encodeURIComponent(threadId)}/messages`, 'POST', { text })}
          onSetStatus={(threadId, action) => threadRequest(`/threads/${encodeURIComponent(threadId)}`, 'PATCH', { action })}
          onViewThread={focusThread}
        />
      </div>
    </div>
  )
}
