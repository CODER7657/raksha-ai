import { Suspense, useEffect, useState } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Menu, X } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { LanguageSelect } from './LanguageSelect'
import { SwissGrid, SWISS_CONTAINER } from './SwissGrid'

const NAV_LINKS = [
  { to: '/app', labelKey: 'nav.scan' },
  { to: '/app/practice', labelKey: 'nav.practice' },
  { to: '/app/chat', labelKey: 'nav.chat' },
  { to: '/app/history', labelKey: 'nav.history' },
  { to: '/app/about', labelKey: 'nav.about' },
]

const SIGN_OUT =
  'inline-flex min-h-11 shrink-0 items-center border-2 border-ink px-4 text-xs font-bold uppercase tracking-[0.08em] text-ink transition-colors hover:bg-ink hover:text-paper'

export function AppShell() {
  const { user, signOut } = useAuth()
  const location = useLocation()
  const { t } = useTranslation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="relative min-h-screen overflow-x-clip bg-paper text-ink">
      {/* The 12-column grid is drawn behind the verdict, where the layout is
          built on it; form and tool pages stay plain. */}
      {location.pathname === '/app/result' && <SwissGrid />}
      <header className="relative z-20 border-b-2 border-rule bg-paper">
        <div className={`${SWISS_CONTAINER} flex items-center justify-between gap-4 py-2`}>
          <Link to="/app" className="flex min-h-11 shrink-0 items-center gap-2">
            <span className="h-3 w-3 bg-accent" aria-hidden="true" />
            <span className="font-display text-lg font-extrabold uppercase tracking-[-0.02em] text-ink">Raksha AI</span>
          </Link>

          <nav className="hidden items-center gap-6 md:flex">
            {NAV_LINKS.map((link) => {
              const current = location.pathname === link.to
              return (
                <Link
                  key={link.to}
                  to={link.to}
                  aria-current={current ? 'page' : undefined}
                  className={`flex min-h-11 items-center border-b-2 text-sm font-medium transition-colors ${
                    current ? 'border-accent text-ink' : 'border-transparent text-ink hover:text-accent'
                  }`}
                >
                  {t(link.labelKey)}
                </Link>
              )
            })}
          </nav>

          <div className="hidden items-center gap-4 md:flex">
            <LanguageSelect />
            <span className="max-w-[180px] truncate text-xs text-ink/70">{user?.email}</span>
            <button type="button" onClick={() => signOut()} className={SIGN_OUT}>
              {t('nav.signOut')}
            </button>
          </div>

          <button
            type="button"
            aria-label={menuOpen ? t('nav.closeMenu') : t('nav.openMenu')}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
            className="-mr-2 flex h-11 w-11 items-center justify-center md:hidden"
          >
            {menuOpen ? <X aria-hidden="true" size={24} /> : <Menu aria-hidden="true" size={24} />}
          </button>
        </div>

        {menuOpen && (
          <div className="border-t border-rule bg-paper md:hidden">
            <div className={`${SWISS_CONTAINER} flex flex-col gap-4 py-4`}>
              <nav className="flex flex-col">
                {NAV_LINKS.map((link) => {
                  const current = location.pathname === link.to
                  return (
                    <Link
                      key={link.to}
                      to={link.to}
                      aria-current={current ? 'page' : undefined}
                      className={`flex min-h-11 items-center border-b border-line text-base font-medium transition-colors ${
                        current ? 'text-accent' : 'text-ink hover:text-accent'
                      }`}
                    >
                      {t(link.labelKey)}
                    </Link>
                  )
                })}
              </nav>
              <LanguageSelect className="w-full" />
              <div className="flex items-center justify-between gap-3 border-t border-line pt-4">
                <span className="truncate text-xs text-ink/70">{user?.email}</span>
                <button type="button" onClick={() => signOut()} className={SIGN_OUT}>
                  {t('nav.signOut')}
                </button>
              </div>
            </div>
          </div>
        )}
      </header>
      <main className={`${SWISS_CONTAINER} relative z-10 py-8 sm:py-12`}>
        <Suspense fallback={null}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  )
}
