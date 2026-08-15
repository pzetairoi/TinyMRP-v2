import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import './App.css'

const PAGE_AUDIT_STORAGE_KEY = 'tinymrp:last-visible-page-audit'
const PAGE_AUDIT_DEDUPE_MS = 2000

function visiblePagePath(pathname: string, search: string): string {
  const source = new URLSearchParams(search)
  const safe = new URLSearchParams()
  for (const key of ['job', 'rev', 'tab']) {
    for (const value of source.getAll(key)) safe.append(key, value)
  }
  const query = safe.toString()
  return `${pathname}${query ? `?${query}` : ''}`
}

/**
 * Layout shell.
 *
 * The skip link is the first focusable thing on every page: a keyboard user
 * landing here would otherwise have to tab through the whole navigation on
 * each navigation to reach the content. It stays visually hidden until it has
 * focus, so it costs sighted users nothing.
 *
 * <main id="main-content"> is the stable target it jumps to, and doubles as
 * the page's landmark for screen readers - previously there was none.
 */
export default function App() {
  const location = useLocation()

  useEffect(() => {
    if (!location.pathname.startsWith('/ui/')) return
    const path = visiblePagePath(location.pathname, location.search)
    const now = Date.now()
    try {
      const previous = JSON.parse(sessionStorage.getItem(PAGE_AUDIT_STORAGE_KEY) || 'null')
      if (previous?.path === path && now - Number(previous?.at || 0) < PAGE_AUDIT_DEDUPE_MS) return
      sessionStorage.setItem(PAGE_AUDIT_STORAGE_KEY, JSON.stringify({ path, at: now }))
    } catch {
      // Storage can be unavailable in hardened browsers. The audit request is
      // still useful; at worst React Strict Mode can duplicate it in dev.
    }
    void fetch('/ui/activity/page-view', {
      method: 'POST',
      credentials: 'same-origin',
      keepalive: true,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    }).catch(() => undefined)
  }, [location.pathname, location.search])

  return (
    <>
      <a className="tm-skip-link" href="#main-content">
        Skip to main content
      </a>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
    </>
  )
}
