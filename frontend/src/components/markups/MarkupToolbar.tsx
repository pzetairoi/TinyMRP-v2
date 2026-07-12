// frontend/src/components/markups/MarkupToolbar.tsx
// Vertical tool rail shown to the left of the markup canvas.
import type { MarkupSaveState, MarkupTool } from './types'

type ToolDef = { tool: MarkupTool; icon: string; label: string }

const TOOLS: ToolDef[] = [
  { tool: 'select', icon: 'pi-bullseye', label: 'Select' },
  { tool: 'pan', icon: 'pi-arrows-alt', label: 'Pan' },
  { tool: 'arrow', icon: 'pi-arrow-up-right', label: 'Arrow' },
  { tool: 'rect', icon: 'pi-stop', label: 'Rectangle' },
  { tool: 'ellipse', icon: 'pi-circle', label: 'Ellipse' },
  { tool: 'cloud', icon: 'pi-cloud', label: 'Revision cloud' },
  { tool: 'text', icon: 'pi-language', label: 'Text / callout' },
  { tool: 'freehand', icon: 'pi-pencil', label: 'Freehand' },
]

const STROKE_WIDTHS = [1, 2, 3, 4, 6, 8]

type Props = {
  tool: MarkupTool
  onToolChange: (tool: MarkupTool) => void
  strokeColor: string
  onStrokeColorChange: (color: string) => void
  strokeWidth: number
  onStrokeWidthChange: (width: number) => void
  canEdit: boolean
  hasSelection: boolean
  canUndo: boolean
  canRedo: boolean
  saveState: MarkupSaveState
  onDelete: () => void
  onUndo: () => void
  onRedo: () => void
}

export default function MarkupToolbar({
  tool,
  onToolChange,
  strokeColor,
  onStrokeColorChange,
  strokeWidth,
  onStrokeWidthChange,
  canEdit,
  hasSelection,
  canUndo,
  canRedo,
  saveState,
  onDelete,
  onUndo,
  onRedo,
}: Props) {
  const editingBlocked = !canEdit || saveState === 'conflict' || saveState === 'saving'
  return (
    <div className="pd-markup-toolbar" role="toolbar" aria-label="Drawing markup tools" aria-orientation="vertical">
      <div className="pd-markup-toolbar-group" aria-label="Markup tools">
        {TOOLS.map((def) => {
          const drawingTool = def.tool !== 'select' && def.tool !== 'pan'
          return (
            <button
              key={def.tool}
              type="button"
              className={`btn btn-sm ${tool === def.tool ? 'btn-primary' : 'btn-outline-secondary'}`}
              title={def.label}
              aria-label={def.label}
              aria-pressed={tool === def.tool}
              disabled={drawingTool ? editingBlocked : saveState === 'conflict'}
              onClick={() => onToolChange(def.tool)}
            >
              <i className={`pi ${def.icon}`} aria-hidden="true" />
            </button>
          )
        })}
      </div>

      <div className="pd-markup-toolbar-sep" role="separator" />

      <div className="pd-markup-toolbar-group" aria-label="Stroke settings">
        <label className="pd-markup-color" title="Stroke colour">
          <span className="visually-hidden">Stroke colour</span>
          <input
            type="color"
            value={strokeColor}
            disabled={editingBlocked}
            onChange={(e) => onStrokeColorChange(e.target.value)}
            aria-label="Stroke colour"
          />
        </label>
        <select
          className="form-select form-select-sm pd-markup-width"
          value={strokeWidth}
          disabled={editingBlocked}
          onChange={(e) => onStrokeWidthChange(Number(e.target.value) || 2)}
          aria-label="Stroke width"
          title="Stroke width"
        >
          {STROKE_WIDTHS.map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
      </div>

      <div className="pd-markup-toolbar-sep" role="separator" />

      <div className="pd-markup-toolbar-group" aria-label="Edit actions">
        <button
          type="button"
          className="btn btn-sm btn-outline-danger"
          title="Delete selected"
          aria-label="Delete selected markup"
          disabled={editingBlocked || !hasSelection}
          onClick={onDelete}
        >
          <i className="pi pi-trash" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          title="Undo"
          aria-label="Undo"
          disabled={editingBlocked || !canUndo}
          onClick={onUndo}
        >
          <i className="pi pi-undo" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          title="Redo"
          aria-label="Redo"
          disabled={editingBlocked || !canRedo}
          onClick={onRedo}
        >
          <i className="pi pi-refresh" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}
