import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import BomPage from './BomPage'
import { mockApi } from '../test/mockApi'

/**
 * QA-FE-01. A BOM that fails to load must not render as an empty tree - that
 * reads as "this assembly has no children", which is a manufacturing answer,
 * not an error message.
 */

const treeRoot = [
  { key: 'PN-1', data: { pn: 'PN-1', rev: 'A', description: 'Top assembly' }, leaf: false },
]

const routes = {
  'GET /api/bom_tree': treeRoot,
  'GET /api/field-config': { contexts: {}, permissions: {} },
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/bom/PN-1/A']}>
      <Routes>
        <Route path="/bom/:pn/:rev" element={<BomPage />} />
      </Routes>
    </MemoryRouter>,
  )

describe('BomPage', () => {
  it('renders the root of the tree', async () => {
    mockApi(routes)
    renderPage()
    expect(await screen.findByText('Top assembly')).toBeInTheDocument()
  })

  it('announces a tree load failure through an alert', async () => {
    // role="alert" so assistive tech is told, not just sighted users.
    mockApi({
      ...routes,
      'GET /api/bom_tree': { status: 500, body: { error: { message: 'BOM service down' } } },
    })
    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('BOM service down')
  })

  it('clears the tree on failure rather than showing stale rows', async () => {
    // setNodes([]) in the catch: a half-rendered previous BOM next to an error
    // would be worse than an empty one.
    mockApi({
      ...routes,
      'GET /api/bom_tree': { status: 500, body: { error: { message: 'boom' } } },
    })
    renderPage()

    await screen.findByRole('alert')
    expect(screen.queryByText('Top assembly')).not.toBeInTheDocument()
  })

  it('tells the user it is loading instead of looking empty', async () => {
    // Large assemblies take seconds. An empty table during that window reads
    // as "this assembly has no children", which is a wrong answer, not a slow
    // one. role="status" so assistive tech is told as well.
    mockApi(routes)
    renderPage()

    expect(screen.getByRole('status')).toHaveTextContent(/loading bom/i)
    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  })

  it('shows no rows while loading, so a slow load cannot read as an empty BOM', async () => {
    // The nodes list is cleared before the request starts. Navigating from a
    // child to its parent used to leave the previous assembly's rows visible.
    mockApi(routes)
    renderPage()

    // While the status indicator is up, no BOM row is on screen yet.
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.queryByText('Top assembly')).not.toBeInTheDocument()

    expect(await screen.findByText('Top assembly')).toBeInTheDocument()
  })
})
