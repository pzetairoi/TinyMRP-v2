import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'

/**
 * Phase 6, E8 — accessibility baseline.
 *
 * Before this, the SPA had no landmark and no way past the navigation with a
 * keyboard. Both are asserted here rather than left to a manual pass, because
 * a skip link is exactly the kind of thing a later refactor deletes without
 * anyone noticing: nobody using a mouse ever sees it.
 */
function renderShell() {
  const router = createMemoryRouter(
    [{ path: '/', element: <App />, children: [{ index: true, element: <p>page body</p> }] }],
    { initialEntries: ['/'] },
  )
  return render(<RouterProvider router={router} />)
}

describe('App shell accessibility', () => {
  it('exposes a main landmark that wraps the page', () => {
    renderShell()

    const main = screen.getByRole('main')
    expect(main).toHaveAttribute('id', 'main-content')
    expect(main).toContainElement(screen.getByText('page body'))
  })

  it('offers a skip link that targets that landmark', () => {
    renderShell()

    expect(screen.getByRole('link', { name: /skip to main content/i })).toHaveAttribute(
      'href',
      '#main-content',
    )
  })

  it('puts the skip link first, or it is useless', () => {
    const { container } = renderShell()

    // A skip link that is not the first focusable element does not save the
    // user any tabbing, which is the only reason it exists.
    const focusable = container.querySelectorAll('a[href], button, input, [tabindex]')
    expect(focusable[0]).toHaveClass('tm-skip-link')
  })
})
