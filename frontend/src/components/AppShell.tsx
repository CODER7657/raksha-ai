import { Outlet, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function AppShell() {
  const { user, signOut } = useAuth()

  return (
    <div className="grid-bg min-h-screen font-mono">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3 sm:px-8 bg-paper/80 backdrop-blur-sm">
        <Link to="/app" className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-sm font-extrabold uppercase tracking-tight text-ink">Raksha AI</span>
        </Link>
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
