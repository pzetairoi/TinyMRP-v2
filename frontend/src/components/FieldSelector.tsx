import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { CSSProperties } from 'react'
import type { FieldDefinition } from '../lib/fieldConfig'

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
    <div className="card shadow-sm">
      <div className="card-body p-3">
        <div className="d-flex align-items-center justify-content-between gap-2 mb-2">
          <div className="fw-semibold small">{title}</div>
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onReset}>
            Reset
          </button>
        </div>
        <div className="d-flex gap-2 mb-2">
          <button type="button" className="btn btn-sm btn-outline-secondary" onClick={selectAll}>
            Select all
          </button>
        </div>
        <div className="row g-2">
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
  const [menuPos, setMenuPos] = useState<{ top: number; left?: number; right?: number } | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)

  function updateMenuPosition() {
    const rect = triggerRef.current?.getBoundingClientRect()
    if (!rect) return
    if (menuAlign === 'start') {
      setMenuPos({ top: rect.bottom + 4, left: Math.max(8, rect.left) })
    } else {
      setMenuPos({ top: rect.bottom + 4, right: Math.max(8, window.innerWidth - rect.right) })
    }
  }

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
            right: menuPos.right,
            zIndex: 2000,
            minWidth: 320,
            maxWidth: 520,
          }}
        >
          <SelectorBody {...props} />
        </div>,
        document.body,
      )}
    </>
  )
}
