import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft } from 'lucide-react'
import { SwissGrid, SWISS_CONTAINER } from '../components/SwissGrid'

/** Catch-all for any URL no route matches.
 *
 * Before this, an unknown path rendered nothing at all: `<Routes>` with no
 * match returns null, so a mistyped or stale link showed a blank page with no
 * way back. Swiss layout (§3 of the roadmap): a giant flush-left "404" on the
 * shared 12-column grid, one rule, one link home. No centring, gradients or shadows. */
export function NotFoundPage() {
  const { t } = useTranslation()
  const { pathname } = useLocation()

  return (
    <main className="relative min-h-screen overflow-x-clip bg-paper text-ink">
      <SwissGrid />
      <div className={`${SWISS_CONTAINER} relative z-10 flex min-h-screen flex-col justify-end pb-16 pt-24 sm:pb-24`}>
        <p
          aria-hidden="true"
          className="font-display text-[clamp(7rem,32vw,18rem)] font-extrabold leading-[0.85] tracking-[-0.06em] text-accent"
        >
          404
        </p>
        <div className="mt-6 h-[3px] w-full bg-rule" />
        <div className="mt-8 grid gap-8 bg-paper sm:grid-cols-12 sm:gap-x-6">
          <div className="sm:col-span-7">
            <h1 className="swiss-display text-[clamp(2rem,6vw,3.5rem)]">
              {t('notFound.title')}
            </h1>
            <p className="mt-4 max-w-prose text-base leading-relaxed text-ink">{t('notFound.body')}</p>
          </div>
          <div className="flex flex-col items-start gap-6 sm:col-span-5">
            <p className="swiss-label text-ink/70">
              {t('notFound.path')}
              <span className="mt-1 block break-all font-mono text-sm font-normal normal-case tracking-normal text-ink">
                {pathname}
              </span>
            </p>
            <Link
              to="/"
              className="inline-flex min-h-11 items-center gap-2 bg-ink px-6 py-3 text-sm font-bold uppercase tracking-[0.08em] text-paper transition-colors hover:bg-accent hover:text-accent-ink"
            >
              <ArrowLeft aria-hidden="true" size={18} />
              {t('notFound.home')}
            </Link>
          </div>
        </div>
      </div>
    </main>
  )
}
