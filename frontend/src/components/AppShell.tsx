import { useEffect, useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { LanguageSelect } from './LanguageSelect'

const NAV_LINKS = [
  { to: '/app', labelKey: 'nav.scan' },
  { to: '/app/practice', labelKey: 'nav.practice' },
  { to: '/app/chat', labelKey: 'nav.chat' },
  { to: '/app/history', labelKey: 'nav.history' },
  { to: '/app/about', labelKey: 'nav.about' },
]

function HamburgerIcon() {
  return (
    <span className="flex flex-col gap-1.5" aria-hidden="true">
      <span className="h-0.5 w-5 bg-ink" />
      <span className="h-0.5 w-5 bg-ink" />
      <span className="h-0.5 w-5 bg-ink" />
    </span>
  )
}

export function AppShell() {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="grid-bg min-h-screen font-mono">
      <header className="relative z-20 border-b border-ink bg-paper/80 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-4 px-4 py-3 sm:px-8">
          <Link to="/app" className="flex items-center gap-2 shrink-0">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-sm font-extrabold uppercase tracking-tight text-ink">Raksha AI</span>
          </Link>

          <nav className="hidden md:flex items-center gap-6">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`text-[11px] font-bold uppercase tracking-[0.1em] transition-colors ${
                  location.pathname === link.to ? 'text-accent' : 'text-ink/60 hover:text-ink'
                }`}
              >
                {t(link.labelKey)}
              </Link>
            ))}
          </nav>

          <div className="hidden md:flex items-center gap-4">
            <LanguageSelect />
            <span className="text-[11px] text-ink/50 truncate max-w-[180px]">{user?.email}</span>
            <button
              onClick={() => signOut()}
              className="border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
            >
              {t('nav.signOut')}
            </button>
          </div>

          <button
            type="button"
            aria-label={menuOpen ? t('nav.closeMenu') : t('nav.openMenu')}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
            className="md:hidden p-2 -mr-2"
          >
            <HamburgerIcon />
          </button>
        </div>

        {menuOpen && (
          <div className="md:hidden border-t border-ink bg-paper px-4 py-4 flex flex-col gap-4">
            <nav className="flex flex-col gap-1">
              {NAV_LINKS.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`py-2 text-xs font-bold uppercase tracking-[0.1em] transition-colors ${
                    location.pathname === link.to ? 'text-accent' : 'text-ink/70 hover:text-ink'
                  }`}
                >
                  {t(link.labelKey)}
                </Link>
              ))}
            </nav>
            <div className="border-t border-line pt-4">
              <LanguageSelect className="w-full" />
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
              <span className="text-[11px] text-ink/50 truncate">{user?.email}</span>
              <button
                onClick={() => signOut()}
                className="shrink-0 border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
              >
                {t('nav.signOut')}
              </button>
            </div>
          </div>
        )}
      </header>
      <main className="px-4 py-8 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
