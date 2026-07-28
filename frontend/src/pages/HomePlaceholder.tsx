import { useAuth } from '../context/AuthContext'

export function HomePlaceholder() {
  const { user, signOut } = useAuth()

  return (
    <div className="grid-bg min-h-screen flex flex-col items-center justify-center gap-4 px-4 font-mono">
      <p className="text-sm text-ink">Signed in as {user?.email}</p>
      <button
        onClick={() => signOut()}
        className="border border-ink px-4 py-2 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
      >
        Sign out
      </button>
    </div>
  )
}
