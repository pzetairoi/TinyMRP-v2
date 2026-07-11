// frontend/src/components/markups/fabricHelpers.ts
// Small helpers around Fabric.js v7 for the drawing markup workspace.
import { Canvas, Group, Line, Path, Triangle } from 'fabric'
import type { MarkupCanvasJson } from './types'

// Custom property persisted with every markup object. Object identity must
// survive save/reload, transforms, undo/redo and thread linking.
export const TM_OBJECT_ID = 'tmObjectId'

export function newObjectId(): string {
  try {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID()
    }
  } catch { /* fall through */ }
  return `tm-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/** Serialize only what the backend accepts: {version, objects}. Objects flagged
 * excludeFromExport (temporary previews, highlights) are dropped by Fabric. */
export function serializeCanvas(canvas: Canvas): MarkupCanvasJson {
  const data = canvas.toObject([TM_OBJECT_ID]) as { version?: string; objects?: any[] }
  return {
    version: typeof data.version === 'string' ? data.version : undefined,
    objects: Array.isArray(data.objects) ? data.objects : [],
  }
}

/** Defensive: after loadFromJSON, make sure every restored object carries the
 * tmObjectId from its JSON source (Fabric passes custom props through, but a
 * missing id must never survive silently). */
export function ensureObjectIds(canvas: Canvas, json: MarkupCanvasJson): void {
  const objects = canvas.getObjects()
  const source = Array.isArray(json?.objects) ? json.objects : []
  objects.forEach((obj: any, idx: number) => {
    if (!obj[TM_OBJECT_ID]) {
      const fromJson = source[idx] && typeof source[idx][TM_OBJECT_ID] === 'string'
        ? source[idx][TM_OBJECT_ID]
        : ''
      obj[TM_OBJECT_ID] = fromJson || newObjectId()
    }
  })
}

export function objectIdsOnCanvas(canvas: Canvas): Set<string> {
  const ids = new Set<string>()
  canvas.getObjects().forEach((obj: any) => {
    if (typeof obj[TM_OBJECT_ID] === 'string' && obj[TM_OBJECT_ID]) ids.add(obj[TM_OBJECT_ID])
  })
  return ids
}

type StrokeOpts = { stroke: string; strokeWidth: number }

/** Arrow = line + head grouped into one selectable logical object. */
export function makeArrow(x1: number, y1: number, x2: number, y2: number, opts: StrokeOpts): Group {
  const { stroke, strokeWidth } = opts
  const headSize = Math.max(10, Math.min(26, strokeWidth * 4 + 8))
  const angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI + 90

  const line = new Line([x1, y1, x2, y2], {
    stroke,
    strokeWidth,
    strokeLineCap: 'round',
    selectable: false,
    evented: false,
  })
  const head = new Triangle({
    left: x2,
    top: y2,
    originX: 'center',
    originY: 'center',
    width: headSize,
    height: headSize,
    angle,
    fill: stroke,
    stroke: '',
    strokeWidth: 0,
    selectable: false,
    evented: false,
  })
  const group = new Group([line, head], {
    // The group is the single selectable arrow object.
    subTargetCheck: false,
    interactive: false,
  })
  return group
}

/** Revision cloud: closed path of semicircular bumps along a rectangle
 * perimeter. Stored as a plain Fabric Path (no SVG/HTML). */
export function makeCloudPath(x: number, y: number, w: number, h: number, opts: StrokeOpts): Path {
  const width = Math.max(20, Math.abs(w))
  const height = Math.max(20, Math.abs(h))
  const target = Math.max(12, Math.min(width, height) / 4)
  const nx = Math.max(2, Math.round(width / target))
  const ny = Math.max(2, Math.round(height / target))
  const sx = width / nx
  const sy = height / ny

  const parts: string[] = [`M ${x} ${y}`]
  const arc = (r: number, ex: number, ey: number) => {
    parts.push(`A ${r} ${r} 0 0 1 ${ex} ${ey}`)
  }
  for (let i = 1; i <= nx; i++) arc(sx / 1.6, x + sx * i, y)
  for (let i = 1; i <= ny; i++) arc(sy / 1.6, x + width, y + sy * i)
  for (let i = nx - 1; i >= 0; i--) arc(sx / 1.6, x + sx * i, y + height)
  for (let i = ny - 1; i >= 0; i--) arc(sy / 1.6, x, y + sy * i)
  parts.push('Z')

  return new Path(parts.join(' '), {
    fill: '',
    stroke: opts.stroke,
    strokeWidth: opts.strokeWidth,
    strokeLineJoin: 'round',
  })
}
