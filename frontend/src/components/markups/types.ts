// frontend/src/components/markups/types.ts

export type MarkupIdentityProfile = {
  email?: string
  display_name?: string
  label?: string
  initials?: string
  avatar_color?: string
  avatar_shape?: string
}

export type MarkupMessage = {
  id: string
  ts: string | null
  ts_display?: string | null
  ts_local?: string | null
  author: string
  author_display?: string
  author_profile?: MarkupIdentityProfile | null
  text: string
}

export type MarkupThreadPriority = 'low' | 'normal' | 'high'
export type MarkupThreadStatus = 'open' | 'resolved'

export type MarkupThread = {
  id: string
  object_ids: string[]
  linked: boolean
  title: string
  priority: MarkupThreadPriority
  status: MarkupThreadStatus
  created_by: string
  created_by_display?: string
  created_by_profile?: MarkupIdentityProfile | null
  created_at: string | null
  created_at_display?: string | null
  created_at_local?: string | null
  updated_by?: string
  updated_at?: string | null
  updated_at_display?: string | null
  resolved_by?: string
  resolved_at?: string | null
  resolved_at_display?: string | null
  messages: MarkupMessage[]
  reply_count: number
}

export type MarkupSource = {
  source_file_id: string
  rel_path: string
  fingerprint: string
  size?: number | null
  mtime?: string | null
}

export type MarkupCanvasJson = {
  version?: string
  objects: any[]
}

export type MarkupLayer = {
  ok: boolean
  part_number: string
  revision: string
  source: MarkupSource
  page_number: number
  version: number
  canvas_schema_version: number
  canvas_json: MarkupCanvasJson
  threads: MarkupThread[]
  open_thread_count: number
  stale_layers_count: number
  can_edit: boolean
  error?: string
  message?: string
}

// PNG rows returned by /api/part_images with source metadata. Drawing PNGs
// are preferred; parts without one can be marked up on their preview PNG.
export type DrawingImageRow = {
  urls: string[]
  revision?: string
  id?: string
  source_file_id?: string
  is_dwg?: boolean
  rel_path?: string
  sha256?: string
  size?: number
  mtime?: string
  source_fingerprint?: string
  /** Full-size image URLs (no thumbnails) for the markup canvas. */
  image_urls?: string[]
}

export type PartCommentPriority = '' | 'low' | 'normal' | 'high'

export type PartCommentReply = {
  id: string
  ts: string | null
  ts_display?: string | null
  ts_local?: string | null
  author: string
  author_display?: string
  author_profile?: MarkupIdentityProfile | null
  text: string
}

// General part comment (no linked markup), unified with markup threads in the
// review panel. Stored in PartAnnotation; markup threads live in the layer.
export type PartCommentRow = {
  id?: string
  ts: string
  ts_display?: string | null
  ts_local?: string | null
  author: string
  author_display?: string
  author_profile?: MarkupIdentityProfile | null
  text: string
  priority?: PartCommentPriority
  status?: 'open' | 'resolved'
  replies?: PartCommentReply[]
  reply_count?: number
}

export type MarkupTool =
  | 'select'
  | 'pan'
  | 'arrow'
  | 'rect'
  | 'ellipse'
  | 'cloud'
  | 'text'
  | 'freehand'

export type MarkupSaveState = 'saved' | 'dirty' | 'saving' | 'conflict'

// Unsaved editor work carried across tab switches (workspace unmount/remount).
export type MarkupDraft = {
  sourceFileId: string
  fingerprint: string
  baseVersion: number
  canvasJson: MarkupCanvasJson
  dirty: boolean
}
