import { render, screen } from '@testing-library/react'
import { Outlet, RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RouteError from './RouteError'
import NotFoundPage from '../pages/NotFoundPage'

/**
 * QA-FE-01 / Phase 6 usability.
 *
 * Two failures that used to be indistinguishable from a working page:
 *   - a render error unmounted the tree and left a BLANK document
 *   - an unknown URL rendered the parts inventory, so a dead link looked like
 *     a successful navigation and was never reported as broken
 *
 * Both assertions below are about what the user SEES, not about internals.
 */

function Boom(): JSX.Element {
  throw new Error('exploded while rendering')
}

function renderAt(path: string, element: JSX.Element) {
  const router = createMemoryRouter(
    [
      {
        path: '/',
        // Mirrors App.tsx: a layout shell whose only job is to render the page.
        element: <Outlet />,
        errorElement: <RouteError />,
        children: [
          { path: '/ui/boom', element },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  return render(<RouterProvider router={router} />)
}

describe('RouteError', () => {
  // React and the router both log the caught error; that is expected here.
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a recoverable message instead of a blank page when a page throws', () => {
    renderAt('/ui/boom', <Boom />)

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText(/something went wrong on this page/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reload/i })).toBeInTheDocument()
  })

  it('surfaces the failure detail, because a user who sees nothing reports nothing', () => {
    renderAt('/ui/boom', <Boom />)

    expect(screen.getByText(/exploded while rendering/)).toBeInTheDocument()
  })

  it('still logs the error for the run logs the owner debugs from', () => {
    renderAt('/ui/boom', <Boom />)

    const logged = (console.error as unknown as ReturnType<typeof vi.fn>).mock.calls
    expect(logged.some((args: unknown[]) => args[0] === 'Unhandled UI error:')).toBe(true)
  })
})

describe('NotFoundPage', () => {
  it('reports the unknown path rather than silently showing another page', () => {
    renderAt('/ui/does-not-exist', <div>never rendered</div>)

    expect(screen.getByText(/page not found/i)).toBeInTheDocument()
    expect(screen.getByText('/ui/does-not-exist')).toBeInTheDocument()
  })

  it('offers a way out', () => {
    renderAt('/ui/does-not-exist', <div>never rendered</div>)

    expect(screen.getByRole('link', { name: /parts inventory/i })).toHaveAttribute('href', '/ui/parts')
    expect(screen.getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', '/ui/dashboard')
  })
})
