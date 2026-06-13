import { useMemo, useState } from 'react'
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
  const { inline = false, buttonLabel = 'Fields' } = props
  const [open, setOpen] = useState(false)

  if (inline) {
    return <SelectorBody {...props} />
  }

  return (
    <div className="position-relative">
      <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => setOpen((v) => !v)}>
        {buttonLabel}
      </button>
      {open && (
        <div
          className="position-absolute end-0 mt-2"
          style={{ zIndex: 20, minWidth: 320, maxWidth: 520 }}
        >
          <SelectorBody {...props} />
        </div>
      )}
    </div>
  )
}
