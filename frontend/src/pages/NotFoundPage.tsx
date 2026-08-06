import { Link, useLocation } from 'react-router-dom'

/**
 * Real 404.
 *
 * The catch-all previously rendered PartsPage, so a mistyped or dead link
 * looked like a SUCCESSFUL navigation to the inventory. That is worse than an
 * error: the user believes they are where they meant to be, and a broken link
 * is never reported because nothing appears broken.
 */
export default function NotFoundPage() {
  const { pathname } = useLocation()

  return (
    <div className="container py-5">
      <h1 className="h4 mb-3">Page not found</h1>
      <p className="text-muted mb-3">
        No page matches <code>{pathname}</code>. The link may be out of date, or the
        address may have a typo.
      </p>
      <Link className="btn btn-primary me-2" to="/ui/parts">
        Parts inventory
      </Link>
      <Link className="btn btn-outline-secondary" to="/ui/dashboard">
        Dashboard
      </Link>
    </div>
  )
}
