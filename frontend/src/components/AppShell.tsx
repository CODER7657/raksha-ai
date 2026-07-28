import { Outlet, Link, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const NAV_LINKS = [
  { to: '/app', label: 'Scan' },
  { to: '/app/history', label: 'History' },
  { to: '/app/about', label: 'About' },
]

export function AppShell() {
  const { user, signOut } = useAuth()
  const location = useLocation()

  return (
    <div className="grid-bg min-h-screen font-mono">
      <header className="flex items-center justify-between gap-4 border-b border-ink px-4 py-3 sm:px-8 bg-paper/80 backdrop-blur-sm">
        <div className="flex items-center gap-6">
          <Link to="/app" className="flex items-center gap-2 shrink-0">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-sm font-extrabold uppercase tracking-tight text-ink">Raksha AI</span>
          </Link>
          <nav className="flex items-center gap-4">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`text-[11px] font-bold uppercase tracking-[0.1em] transition-colors ${
                  location.pathname === link.to ? 'text-accent' : 'text-ink/60 hover:text-ink'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden sm:inline text-[11px] text-ink/50 truncate max-w-[180px]">{user?.email}</span>
          <button
            onClick={() => signOut()}
            className="border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
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
