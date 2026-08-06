import { isRouteErrorResponse, useRouteError } from 'react-router-dom'

/**
 * Route-level error boundary.
 *
 * Without this, a render error anywhere in a page unmounts the whole tree and
 * leaves a BLANK document with no message — indistinguishable from "still
 * loading" or "the server is down". Wired as `errorElement` on the root route
 * so it covers every page.
 *
 * The message is shown on purpose: this is an internal engineering tool whose
 * users report problems by describing what they saw. A blank page produces no
 * report at all.
 */
export default function RouteError() {
  const error = useRouteError()

  let detail = ''
  if (isRouteErrorResponse(error)) detail = `${error.status} ${error.statusText}`
  else if (error instanceof Error) detail = error.message
  else if (typeof error === 'string') detail = error

  // The stack never reaches the UI, but the owner debugs from run logs.
  console.error('Unhandled UI error:', error)

  return (
    <div className="container py-5" role="alert">
      <h1 className="h4 mb-3">Something went wrong on this page</h1>
      <p className="text-muted mb-3">
        The rest of the application is unaffected. Reloading usually clears it; if it
        does not, the detail below identifies where it failed.
      </p>
      {detail && <pre className="bg-light border rounded p-3 mb-3 small">{detail}</pre>}
      <button type="button" className="btn btn-primary me-2" onClick={() => window.location.reload()}>
        Reload
      </button>
      <a className="btn btn-outline-secondary" href="/ui/parts">
        Back to parts
      </a>
    </div>
  )
}
