import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties } from 'react'
import type { FieldDefinition } from '../lib/fieldConfig'

const MENU_MARGIN = 8
const MENU_DEFAULT_WIDTH = 320
const MENU_MIN_HEIGHT = 160

type MenuPosition = { top: number; left: number; maxHeight: number }

function computeMenuPosition(
  triggerRect: DOMRect,
  menuAlign: 'start' | 'end',
  menuSize: { width: number; height: number } | null,
): MenuPosition {
  const viewportW = window.innerWidth
  const viewportH = window.innerHeight
  const width = menuSize?.width ?? MENU_DEFAULT_WIDTH

  let left = menuAlign === 'start' ? triggerRect.left : triggerRect.right - width
  left = Math.max(MENU_MARGIN, Math.min(left, viewportW - width - MENU_MARGIN))

  const spaceBelow = viewportH - triggerRect.bottom - MENU_MARGIN
  const spaceAbove = triggerRect.top - MENU_MARGIN
  // Only flip upward once we know the menu's real height (post-mount) and it
  // would genuinely fit better above the trigger than below it.
  const openUpward = !!menuSize && menuSize.height > spaceBelow && spaceAbove > spaceBelow

  const maxHeight = Math.max(MENU_MIN_HEIGHT, openUpward ? spaceAbove : spaceBelow)
  const top = openUpward
    ? Math.max(MENU_MARGIN, triggerRect.top - 4 - Math.min(menuSize!.height, maxHeight))
    : triggerRect.bottom + 4

  return { top, left, maxHeight }
}

type Props = {
  title: string
  availableFields: FieldDefinition[]
  selectedIds: string[]
  requiredIds?: string[]
  onChange: (fieldIds: string[]) => void
  onReset: () => void
  inline?: boolean
  buttonLabel?: string
  buttonIcon?: string
  buttonClassName?: string
  buttonStyle?: CSSProperties
  menuAlign?: 'start' | 'end'
}

function SelectorBody({
  title,
  availableFields,
  selectedIds,
  requiredIds = [],
  onChange,
  onReset,
}: Omit<Props, 'inline' | 'buttonLabel'>) {
  const required = useMemo(() => new Set(requiredIds), [requiredIds])
  const selected = useMemo(() => new Set(selectedIds), [selectedIds])

  function toggleField(fieldId: string, checked: boolean) {
    if (!checked && required.has(fieldId)) return
    const next = availableFields
      .map((field) => field.id)
      .filter((field) => (field === fieldId ? checked : selected.has(field)))
    onChange(next)
  }

  function selectAll() {
    onChange(availableFields.map((field) => field.id))
  }

  return (
    <div className="card shadow-sm" style={{ display: 'flex', flexDirection: 'column', maxHeight: '100%' }}>
      <div className="card-body p-3" style={{ display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
        <div className="d-flex align-items-center justify-content-between gap-2 mb-2" style={{ flex: '0 0 auto' }}>
          <div className="fw-semibold small">{title}</div>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onReset}>
            Reset
          </button>
        </div>
        <div className="d-flex gap-2 mb-2" style={{ flex: '0 0 auto' }}>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={selectAll}>
            Select all
          </button>
        </div>
        <div className="row g-2" style={{ overflowY: 'auto', minHeight: 0, margin: 0 }}>
          {availableFields.map((field) => (
            <div key={field.id} className="col-12 col-md-6">
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id={`${title}-${field.id}`}
                  checked={selected.has(field.id)}
                  disabled={required.has(field.id)}
                  onChange={(e) => toggleField(field.id, e.target.checked)}
                />
                <label className="form-check-label small" htmlFor={`${title}-${field.id}`}>
                  {field.label}
                  {required.has(field.id) ? ' (required)' : ''}
                </label>
              </div>
            </div>
          ))}
          {!availableFields.length && <div className="text-muted small">No configurable fields.</div>}
        </div>
      </div>
    </div>
  )
}

export default function FieldSelector(props: Props) {
  const {
    inline = false,
    buttonLabel = 'Fields',
    buttonIcon,
    buttonClassName = 'btn btn-sm btn-outline-secondary',
    buttonStyle,
    menuAlign = 'end',
  } = props
  const [open, setOpen] = useState(false)
  const [menuPos, setMenuPos] = useState<MenuPosition | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  function updateMenuPosition() {
    const rect = triggerRef.current?.getBoundingClientRect()
    if (!rect) return
    const menuRect = menuRef.current?.getBoundingClientRect()
    setMenuPos(computeMenuPosition(rect, menuAlign, menuRect ? { width: menuRect.width, height: menuRect.height } : null))
  }

  // First pass (on click, before mount) places the menu using a guessed width
  // and caps it to the space below the trigger, so it's always at least
  // scrollable-accessible. This second pass re-measures the mounted menu's
  // real size and corrects the position/flip before the browser paints, so
  // there's no visible jump.
  useLayoutEffect(() => {
    if (!open) return
    updateMenuPosition()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      const target = e.target as Node
      if (triggerRef.current?.contains(target)) return
      if (menuRef.current?.contains(target)) return
      setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('mousedown', onPointerDown)
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('resize', updateMenuPosition)
    window.addEventListener('scroll', updateMenuPosition, true)
    return () => {
      window.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('resize', updateMenuPosition)
      window.removeEventListener('scroll', updateMenuPosition, true)
    }
  }, [open, menuAlign])

  if (inline) {
    return <SelectorBody {...props} />
  }

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={buttonClassName}
        style={buttonStyle}
        onClick={() => {
          if (!open) updateMenuPosition()
          setOpen((v) => !v)
        }}
      >
        {buttonIcon && <i className={buttonIcon} aria-hidden="true" />}
        {buttonLabel}
      </button>
      {open && menuPos && createPortal(
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            top: menuPos.top,
            left: menuPos.left,
            zIndex: 2000,
            minWidth: 320,
            maxWidth: 520,
            maxHeight: menuPos.maxHeight,
            overflow: 'hidden',
          }}
        >
          <SelectorBody {...props} />
        </div>,
        document.body,
      )}
    </>
  )
}
