import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

/** Catch-all for any URL no route matches.
 *
 * Before this, an unknown path rendered nothing at all: `<Routes>` with no
 * match returns null, so a mistyped or stale link showed a blank page with no
 * way back. Swiss layout (§3 of the roadmap): a giant flush-left "404" on the
 * shared grid, one rule, one link home. No centring, gradients or shadows. */
export function NotFoundPage() {
  const { t } = useTranslation()
  const { pathname } = useLocation()

  return (
    <main className="grid-bg min-h-screen font-mono text-ink">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col justify-end px-6 pb-16 pt-24 sm:px-10 sm:pb-24">
        <p
          aria-hidden="true"
          className="font-sans text-[clamp(7rem,32vw,18rem)] font-extrabold leading-[0.85] tracking-[-0.06em]"
        >
          404
        </p>
        <div className="mt-6 h-[3px] w-full bg-ink" />
        <div className="mt-8 grid gap-8 sm:grid-cols-12">
          <div className="sm:col-span-7">
            <h1 className="font-sans text-3xl font-extrabold uppercase leading-[0.95] tracking-tight sm:text-5xl">
              {t('notFound.title')}
            </h1>
            <p className="mt-4 max-w-prose text-sm leading-relaxed text-ink/80">{t('notFound.body')}</p>
          </div>
          <div className="flex flex-col items-start gap-6 sm:col-span-5">
            <p className="text-[11px] uppercase tracking-[0.2em] text-ink/70">
              {t('notFound.path')}
              <span className="mt-1 block break-all font-bold normal-case tracking-normal text-ink">
                {pathname}
              </span>
            </p>
            <Link
              to="/"
              className="inline-flex min-h-11 items-center bg-ink px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-paper transition-colors hover:bg-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {t('notFound.home')}
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
