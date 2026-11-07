import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Menu, X } from 'lucide-react'
import { TiltCard } from '../components/TiltCard'
import { SwissGrid, SWISS_CONTAINER } from '../components/SwissGrid'

const FEATURES = [
  {
    title: 'RAG-grounded detection',
    body: 'Every message is checked against a real vector database of known scam patterns before the AI judges it — not a raw guess.',
  },
  {
    // "12 Indian languages" flat was an overclaim, and the benchmark said so:
    // eight of the twelve have detection rules no speaker of that language has
    // read. Stating the shape of the coverage is both more honest and a
    // stronger claim than a bare number — because the part that *is* reviewed
    // is the part most Indian scam SMS actually uses.
    title: '12 Indian languages',
    body: 'English, Hindi, Gujarati, Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia, Urdu. English and mixed-script messages are checked everywhere; the word lists for three are speaker-reviewed, and the rest are being read now.',
  },
  {
    title: 'Voice & text scans',
    body: 'Paste a message or upload/record a call — same grounded analysis either way.',
  },
  {
    title: 'Community Scam Radar',
    body: 'See how many people nearby reported the same scam this week — anonymized, aggregate.',
  },
  {
    title: 'Works when the AI can’t',
    body: 'An offline pattern check flags obvious scams instantly, even with no connection.',
  },
  {
    title: 'Your data stays yours',
    body: 'Row-level security means no one, not even another logged-in user, can see your scan history.',
  },
]

const STEPS = [
  { n: '01', title: 'Paste or record', body: 'Drop in a suspicious SMS, WhatsApp message, or a call snippet.' },
  { n: '02', title: 'We check it', body: 'Retrieval-grounded AI scores it against known scam patterns in your language.' },
  { n: '03', title: 'Know what to do', body: 'Get a plain-language explanation and one clear next step.' },
]

const LANGUAGES = [
  'English', 'हिन्दी', 'ગુજરાતી', 'मराठी', 'বাংলা', 'தமிழ்',
  'తెలుగు', 'ಕನ್ನಡ', 'മലയാളം', 'ਪੰਜਾਬੀ', 'ଓଡ଼ିଆ', 'اردو',
]

const STACK = [
  { name: 'Supabase', role: 'DB + Auth + vector store' },
  { name: 'Groq', role: 'primary LLM' },
  { name: 'Gemini', role: 'fallback LLM' },
  { name: 'Vercel', role: 'frontend hosting' },
  { name: 'Render', role: 'backend hosting' },
  { name: 'GitHub Actions', role: 'CI/CD' },
]

const NAV_LINKS = [
  { href: '#features', label: 'Features' },
  { href: '#languages', label: 'Languages' },
  { href: '#how-it-works', label: 'How it works' },
  { href: '#stack', label: 'Free stack' },
]

const SECTION = `${SWISS_CONTAINER} relative grid grid-cols-12 gap-x-4 sm:gap-x-6 border-t-2 border-rule py-16 sm:py-24 scroll-mt-20`
const PRIMARY_CTA =
  'inline-flex min-h-11 items-center gap-2 bg-accent px-6 py-3 text-sm font-bold uppercase tracking-[0.08em] text-accent-ink transition-colors hover:bg-ink'
const SECONDARY_CTA =
  'inline-flex min-h-11 items-center gap-2 border-2 border-ink px-6 py-3 text-sm font-bold uppercase tracking-[0.08em] text-ink transition-colors hover:bg-ink hover:text-paper'

/** Section number + label in the left columns, content in the right. */
function SectionHead({ n, label }: { n: string; label: string }) {
  return (
    <div className="col-span-12 mb-8 md:col-span-3 md:mb-0">
      <p className="font-display text-5xl font-extrabold leading-none tracking-[-0.04em] text-accent" aria-hidden="true">
        {n}
      </p>
      <h2 className="swiss-label mt-3 font-sans text-ink">{label}</h2>
    </div>
  )
}

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="relative min-h-screen overflow-x-clip bg-paper text-ink">
      <SwissGrid />

      <header className="sticky top-0 z-20 border-b-2 border-rule bg-paper">
        <div className={`${SWISS_CONTAINER} flex items-center justify-between gap-4 py-2`}>
          <Link to="/" className="flex min-h-11 items-center gap-2">
            <span className="h-3 w-3 bg-accent" aria-hidden="true" />
            <span className="font-display text-lg font-extrabold uppercase tracking-[-0.02em]">Raksha AI</span>
          </Link>

          <nav className="hidden items-center gap-6 md:flex" aria-label="Page sections">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="flex min-h-11 items-center text-sm font-medium text-ink transition-colors hover:text-accent"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <Link
            to="/login"
            className="hidden min-h-11 items-center border-2 border-ink px-4 text-sm font-bold uppercase tracking-[0.08em] text-ink transition-colors hover:bg-ink hover:text-paper md:inline-flex"
          >
            Log in
          </Link>

          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
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
              <nav className="flex flex-col" aria-label="Page sections">
                {NAV_LINKS.map((link) => (
                  <a
                    key={link.href}
                    href={link.href}
                    onClick={() => setMenuOpen(false)}
                    className="flex min-h-11 items-center border-b border-line text-base font-medium text-ink hover:text-accent"
                  >
                    {link.label}
                  </a>
                ))}
              </nav>
              <Link to="/login" onClick={() => setMenuOpen(false)} className={SECONDARY_CTA}>
                Log in
              </Link>
            </div>
          </div>
        )}
      </header>

      <main className="relative z-10">
        {/* Hero. The `short:` variants are the fix for #12's second half. `sm:`
            keys off width alone, so a phone in landscape (667x375) gets desktop
            padding and a 60px heading inside a 375px-tall window — the CTA
            landed 217px below the fold. Height has to be part of the
            condition, not inferred from width. */}
        <section
          className={`${SWISS_CONTAINER} grid grid-cols-12 gap-x-4 gap-y-10 py-14 sm:gap-x-6 sm:py-24 short:gap-y-4 short:py-6`}
        >
          <div className="col-span-12 lg:col-span-9">
            <p className="swiss-label mb-6 flex items-center gap-2 text-ink short:mb-2">
              <span className="h-2 w-2 bg-accent" aria-hidden="true" />
              Financial Safety for Rural India
            </p>
            <h1 className="swiss-display text-[clamp(2.75rem,10vw,7rem)] short:text-[clamp(2rem,6vw,3rem)]">
              Spot the scam
              <br />
              <span className="text-accent">before it costs you</span>
            </h1>
          </div>

          <div className="col-span-12 md:col-span-7 lg:col-span-6">
            <p className="max-w-md text-base leading-relaxed text-ink sm:text-lg">
              Paste a message, a UPI request, or a call recording. Raksha AI checks it against real
              scam patterns and tells you — in your own language — exactly what to do next.
            </p>
            <div className="mt-8 flex flex-wrap gap-3 short:mt-4">
              <Link to="/login" className={PRIMARY_CTA}>
                Get started — free
                <ArrowRight aria-hidden="true" size={18} />
              </Link>
              <a href="#how-it-works" className={SECONDARY_CTA}>
                How it works
              </a>
            </div>
          </div>

          {/* The graphic is type, not a picture: the coverage number, set as
              large as the headline. Tilts only for a mouse and only when the
              system allows motion (TiltCard). */}
          <TiltCard className="col-span-12 md:col-span-5 md:col-start-8 lg:col-span-4 lg:col-start-9 short:hidden">
            <div className="border-t-8 border-accent bg-paper pt-4" aria-hidden="true">
              <p className="font-display text-[clamp(6rem,24vw,12rem)] font-extrabold leading-[0.8] tracking-[-0.06em] text-ink">
                12
              </p>
              {/* Not a bare "12 Indian languages": only three of the twelve have
                  word lists a speaker has reviewed (see the feature card above),
                  so the qualifier sits next to the number, not a scroll away. */}
              <p className="swiss-label mt-4 text-ink">Languages checked</p>
              <p className="mt-2 text-sm text-ink/70">3 speaker-reviewed: English, Hindi, Gujarati</p>
            </div>
          </TiltCard>
        </section>

        {/* Feature grid */}
        <section id="features" className={SECTION}>
          <SectionHead n="01" label="What makes it different" />
          <ul className="col-span-12 grid gap-x-6 gap-y-10 sm:grid-cols-2 md:col-span-9 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <li key={f.title} className="border-t border-rule bg-paper pt-4">
                <h3 className="text-xl">{f.title}</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-ink/80">{f.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* Languages */}
        <section id="languages" className={SECTION}>
          <SectionHead n="02" label="Speaks your language" />
          <div className="col-span-12 md:col-span-9">
            <p className="mb-10 max-w-2xl bg-paper text-base leading-relaxed text-ink sm:text-lg">
              Scan results come back in the same language you scanned in — no translation gap between
              what a scammer wrote and what you understand.
            </p>
            <ul className="grid grid-cols-2 border-t border-rule sm:grid-cols-3 lg:grid-cols-4">
              {LANGUAGES.map((lang) => (
                <li key={lang} className="border-b border-line bg-paper py-4 pr-4 text-xl font-bold">
                  {lang}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className={SECTION}>
          <SectionHead n="03" label="How it works" />
          <div className="col-span-12 md:col-span-9">
            <ol className="grid gap-10 sm:grid-cols-3 sm:gap-6">
              {STEPS.map((s) => (
                <li key={s.n} className="border-t-2 border-rule bg-paper pt-4">
                  <span className="font-display text-6xl font-extrabold leading-none tracking-[-0.04em] text-accent">
                    {s.n}
                  </span>
                  <h3 className="mt-4 text-2xl">{s.title}</h3>
                  <p className="mt-3 text-[15px] leading-relaxed text-ink/80">{s.body}</p>
                </li>
              ))}
            </ol>
            <Link to="/login" className={`mt-12 ${PRIMARY_CTA}`}>
              Try it now
              <ArrowRight aria-hidden="true" size={18} />
            </Link>
          </div>
        </section>

        {/* Free stack */}
        <section id="stack" className={SECTION}>
          <SectionHead n="04" label="Built free, forever" />
          <div className="col-span-12 md:col-span-9">
            <p className="mb-10 max-w-2xl bg-paper text-base leading-relaxed text-ink sm:text-lg">
              Every layer runs on a free tier — no card, no hidden cost, nothing that breaks at scale
              without a plan to pay for it.
            </p>
            <dl className="grid grid-cols-2 border-t border-rule sm:grid-cols-3">
              {STACK.map((s) => (
                <div key={s.name} className="border-b border-line bg-paper py-4 pr-4">
                  <dt className="text-base font-bold">{s.name}</dt>
                  <dd className="mt-1 text-sm text-ink/70">{s.role}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t-2 border-rule bg-paper">
        <p className={`${SWISS_CONTAINER} py-6 text-sm text-ink/70`}>Free for every citizen, always.</p>
      </footer>
    </div>
  )
}
