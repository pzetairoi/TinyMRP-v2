import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FieldDefinition } from '../lib/fieldConfig'
import FieldSelector from './FieldSelector'
import { computeMenuPosition } from '../lib/menuPosition'

/**
 * QA-FE-01. Two things are worth pinning here.
 *
 * The menu geometry, because an off-screen or clipped dropdown is a recurring
 * UI bug and it is pure arithmetic - far cheaper to test directly than through
 * a rendered portal.
 *
 * The required-field rule, because fieldConfig.ts enforces it in the data
 * layer but the checkbox is what the user actually touches. Both have to hold,
 * or the UI lets someone remove a column the backend insists on.
 */

const rect = (over: Partial<DOMRect> = {}): DOMRect =>
  ({
    top: 100, bottom: 130, left: 200, right: 400,
    width: 200, height: 30, x: 200, y: 100,
    ...over,
  }) as DOMRect

const fields: FieldDefinition[] = [
  { id: 'pn', label: 'Part number' },
  { id: 'rev', label: 'Revision' },
  { id: 'desc', label: 'Description' },
] as unknown as FieldDefinition[]

describe('computeMenuPosition', () => {
  beforeEach(() => {
    vi.stubGlobal('innerWidth', 1000)
    vi.stubGlobal('innerHeight', 800)
  })

  it('opens below the trigger by default', () => {
    expect(computeMenuPosition(rect(), 'start', null).top).toBe(134)
  })

  it('aligns to the trigger start or end', () => {
    expect(computeMenuPosition(rect(), 'start', { width: 320, height: 200 }).left).toBe(200)
    expect(computeMenuPosition(rect(), 'end', { width: 320, height: 200 }).left).toBe(80)
  })

  it('keeps the menu on screen when the trigger is near an edge', () => {
    // The bug this guards: a right-aligned menu next to the viewport edge
    // rendering half outside it.
    const nearRight = rect({ left: 950, right: 990 })
    const { left } = computeMenuPosition(nearRight, 'start', { width: 320, height: 200 })
    expect(left).toBeGreaterThanOrEqual(8)
    expect(left + 320).toBeLessThanOrEqual(1000)
  })

  it('flips upward only once the real height is known and it fits better', () => {
    const nearBottom = rect({ top: 700, bottom: 730 })
    // Pre-measurement: must not flip, or the menu jumps on first paint.
    expect(computeMenuPosition(nearBottom, 'start', null).top).toBe(734)
    // Post-measurement with more room above than below.
    expect(computeMenuPosition(nearBottom, 'start', { width: 320, height: 400 }).top).toBeLessThan(700)
  })

  it('never returns a maxHeight below the readable minimum', () => {
    const noRoom = rect({ top: 395, bottom: 405 })
    vi.stubGlobal('innerHeight', 410)
    expect(computeMenuPosition(noRoom, 'start', null).maxHeight).toBeGreaterThanOrEqual(160)
  })
})

describe('FieldSelector', () => {
  function renderInline(over: Partial<Parameters<typeof FieldSelector>[0]> = {}) {
    const onChange = vi.fn()
    render(
      <FieldSelector
        title="Columns"
        availableFields={fields}
        selectedIds={['pn', 'rev']}
        requiredIds={['pn']}
        onChange={onChange}
        onReset={vi.fn()}
        inline
        {...over}
      />,
    )
    return { onChange }
  }

  // getAllBy*, not getBy*: the selector renders its field list more than once
  // (responsive layout), which is a presentation detail these tests should not
  // depend on. The first checkbox for a label is representative.
  const box = (label: RegExp) => screen.getAllByLabelText(label)[0]

  it('checks the selected fields and leaves the rest unchecked', () => {
    renderInline()
    // Partial match: required fields render as "Part number (required)".
    expect(box(/Part number/)).toBeChecked()
    expect(box(/Description/)).not.toBeChecked()
  })

  it('disables required fields and marks them as such in the label', () => {
    renderInline()
    expect(box(/Part number \(required\)/)).toBeDisabled()
    expect(box(/Revision/)).toBeEnabled()
  })

  it('reports an added field to the caller', () => {
    const { onChange } = renderInline()
    fireEvent.click(box(/Description/))
    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining(['desc']))
  })

  it('reports a removed field to the caller', () => {
    const { onChange } = renderInline()
    fireEvent.click(box(/Revision/))
    expect(onChange).toHaveBeenCalledWith(expect.not.arrayContaining(['rev']))
  })
})
