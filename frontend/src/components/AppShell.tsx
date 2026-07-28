import { Outlet, Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_LINKS = [
  { to: '/app', label: 'Scan' },
  { to: '/app/history', label: 'History' },
  { to: '/app/about', label: 'About' },
  { to: '/app/practice', label: 'Practice' },
]

export function AppShell() {
  const { user, signOut } = useAuth()
  const location = useLocation()

  return (
    <div className="grid-bg min-h-screen font-mono">
      {/* Matches LandingPage's header exactly (padding, logo dot/text size,
          button treatment) — this is the same "taskbar" the user sees
          before and after logging in, it should never look like two
          different apps. */}
      <header className="flex items-center justify-between gap-4 border-b border-ink px-4 py-4 sm:px-8 sm:py-5 bg-paper/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-4 sm:gap-6 min-w-0">
          <Link to="/app" className="flex items-center gap-2 shrink-0">
            <span className="h-2.5 w-2.5 bg-accent" aria-hidden="true" />
            {/* Logo text hidden below sm to leave room for the nav links —
                at 375px there isn't space for "Raksha AI" + 3 nav links +
                Sign out without one of them getting squeezed into a
                horizontal scroll, and the nav is more important than the
                wordmark once you're already inside the app. */}
            <span className="hidden sm:inline text-base font-extrabold uppercase tracking-tight text-ink">
              Raksha AI
            </span>
          </Link>
          <nav className="flex items-center gap-3 sm:gap-6 min-w-0">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`shrink-0 text-[11px] font-bold uppercase tracking-[0.1em] transition-colors ${
                  location.pathname === link.to ? 'text-accent' : 'text-ink/60 hover:text-ink'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <span className="hidden lg:inline text-[11px] text-ink/50 truncate max-w-[180px]">{user?.email}</span>
          <button
            onClick={() => signOut()}
            className="border border-ink px-3 sm:px-4 py-2 text-[11px] font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="px-4 py-8 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
