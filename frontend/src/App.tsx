import { Outlet } from 'react-router-dom'
import './App.css'

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
