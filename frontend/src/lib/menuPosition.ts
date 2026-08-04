const MENU_MARGIN = 8
const MENU_DEFAULT_WIDTH = 320
const MENU_MIN_HEIGHT = 160

export type MenuPosition = { top: number; left: number; maxHeight: number }

/**
 * Place a dropdown next to its trigger without letting it leave the viewport.
 *
 * Lives here rather than beside the component so it can be exported for tests
 * without breaking react-refresh, which requires a component file to export
 * only components.
 */
export function computeMenuPosition(
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
  // Only flip upward once the menu's real height is known (post-mount) and it
  // would genuinely fit better above the trigger than below it. Flipping on the
  // first, guessed pass makes the menu visibly jump.
  const openUpward = !!menuSize && menuSize.height > spaceBelow && spaceAbove > spaceBelow

  const maxHeight = Math.max(MENU_MIN_HEIGHT, openUpward ? spaceAbove : spaceBelow)
  const top = openUpward
    ? Math.max(MENU_MARGIN, triggerRect.top - 4 - Math.min(menuSize!.height, maxHeight))
    : triggerRect.bottom + 4

  return { top, left, maxHeight }
}
