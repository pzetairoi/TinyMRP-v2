import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import NotFoundPage from './NotFoundPage'

/**
 * The defect this page exists to prevent, and therefore what this test pins:
 * the catch-all route used to render PartsPage, so a dead or mistyped link
 * looked like a SUCCESSFUL navigation to the inventory.
 *
 * That is worse than an error. The user believes they are where they meant to
 * be, and the broken link is never reported because nothing appears broken.
 * So the assertions below are about the page being unmistakably a 404 and
 * naming the path that failed - not about its styling.
 */

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <NotFoundPage />
    </MemoryRouter>,
  )

describe('NotFoundPage', () => {
  it('says the page was not found rather than rendering something plausible', () => {
    renderAt('/ui/does-not-exist')

    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
    // It must not look like the inventory it used to silently render.
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('names the path that failed, so a broken link can actually be reported', () => {
    renderAt('/ui/part/TYPO-123')

    expect(screen.getByText('/ui/part/TYPO-123')).toBeInTheDocument()
  })

  it('offers a way out instead of stranding the user', () => {
    renderAt('/ui/nowhere')

    const parts = screen.getByRole('link', { name: /parts inventory/i })
    const dashboard = screen.getByRole('link', { name: /dashboard/i })
    expect(parts).toHaveAttribute('href', '/ui/parts')
    expect(dashboard).toHaveAttribute('href', '/ui/dashboard')
  })
})
