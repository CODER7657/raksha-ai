import { useState } from 'react'
import { Link } from 'react-router-dom'
import { TiltCard } from '../components/TiltCard'
import { CornerBrackets } from '../components/CornerBrackets'

const FEATURES = [
  {
    title: 'RAG-grounded detection',
    body: 'Every message is checked against a real vector database of known scam patterns before the AI judges it — not a raw guess.',
  },
  {
    title: '12 Indian languages',
    body: 'English, Hindi, Gujarati, Marathi, Bengali, Tamil, Telugu, Kannada, Malayalam, Punjabi, Odia, Urdu.',
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

function HamburgerIcon() {
  return (
    <span className="flex flex-col gap-1.5" aria-hidden="true">
      <span className="h-0.5 w-5 bg-ink" />
      <span className="h-0.5 w-5 bg-ink" />
      <span className="h-0.5 w-5 bg-ink" />
    </span>
  )
}

export function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="grid-bg min-h-screen font-mono text-ink">
      <header className="border-b border-ink bg-paper/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center justify-between px-4 py-4 sm:px-8 sm:py-5">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 bg-accent" aria-hidden="true" />
            <span className="text-base font-extrabold uppercase tracking-tight">Raksha AI</span>
          </div>

          <nav className="hidden md:flex items-center gap-6" aria-label="Page sections">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-[11px] font-bold uppercase tracking-[0.1em] text-ink/60 hover:text-accent transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <Link
            to="/login"
            className="hidden md:inline-block border border-ink px-4 py-2 text-[11px] font-bold uppercase tracking-[0.15em] hover:bg-ink hover:text-white transition-colors"
          >
            Log in
          </Link>

          <button
            type="button"
            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((o) => !o)}
            className="md:hidden p-2 -mr-2"
          >
            <HamburgerIcon />
          </button>
        </div>

        {menuOpen && (
          <div className="md:hidden border-t border-ink bg-paper px-4 py-4 flex flex-col gap-4">
            <nav className="flex flex-col gap-1" aria-label="Page sections">
              {NAV_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  onClick={() => setMenuOpen(false)}
                  className="py-2 text-xs font-bold uppercase tracking-[0.1em] text-ink/70 hover:text-accent transition-colors"
                >
                  {link.label}
                </a>
              ))}
            </nav>
            <Link
              to="/login"
              onClick={() => setMenuOpen(false)}
              className="border border-ink px-4 py-2 text-center text-[11px] font-bold uppercase tracking-[0.15em] hover:bg-ink hover:text-white transition-colors"
            >
              Log in
            </Link>
          </div>
        )}
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 sm:px-8 py-20 sm:py-28 grid gap-12 md:grid-cols-2 md:items-center">
          <div>
            <div className="flex items-center gap-2 mb-5">
              <span className="h-2 w-2 bg-accent" aria-hidden="true" />
              <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
                Maverick Effect AI Challenge
              </span>
            </div>
            <h1 className="text-4xl sm:text-6xl font-extrabold uppercase tracking-tight leading-[0.95]">
              Spot the scam
              <br />
              before it costs you
            </h1>
            <p className="mt-5 text-sm sm:text-base text-ink/70 leading-relaxed max-w-md">
              Paste a message, a UPI request, or a call recording. Raksha AI checks it against real
              scam patterns and tells you — in your own language — exactly what to do next.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/login"
                className="bg-accent px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
              >
                Get started — free
              </Link>
              <a
                href="#how-it-works"
                className="border border-ink px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] hover:bg-ink hover:text-white transition-colors"
              >
                How it works
              </a>
            </div>
          </div>

          {/* 3D tilt hero visual: layered shield with real depth via translateZ */}
          <TiltCard className="mx-auto w-full max-w-sm aspect-square [transform-style:preserve-3d]">
            <div className="relative h-full w-full [transform-style:preserve-3d]">
              <div
                className="absolute inset-0 border border-line bg-paper"
                style={{ transform: 'translateZ(0px)' }}
              />
              <div
                className="absolute inset-6 border border-ink/30"
                style={{ transform: 'translateZ(30px)' }}
                aria-hidden="true"
              >
                <CornerBrackets />
              </div>
              <div
                className="absolute inset-16 flex items-center justify-center bg-paper"
                style={{ transform: 'translateZ(70px)' }}
              >
                <img
                  src="/shield-hero.webp"
                  alt="Raksha AI shield"
                  className="h-full w-full object-contain drop-shadow-[0_18px_28px_rgba(0,0,0,0.3)]"
                  draggable={false}
                />
              </div>
              <span
                className="absolute -top-2 -right-2 h-3 w-3 bg-accent"
                style={{ transform: 'translateZ(90px)' }}
                aria-hidden="true"
              />
            </div>
          </TiltCard>
        </section>

        {/* Feature grid */}
        <section id="features" className="mx-auto max-w-6xl px-4 sm:px-8 pb-20 sm:pb-28 scroll-mt-20">
          <div className="flex items-center gap-2 mb-8">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">What makes it different</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="relative border border-ink bg-paper/60 p-5 transition-transform duration-150 hover:-translate-y-1 hover:shadow-[6px_6px_0_0_var(--color-ink)]"
              >
                <CornerBrackets />
                <h3 className="text-xs font-bold uppercase tracking-[0.1em] mb-2">{f.title}</h3>
                <p className="text-[13px] text-ink/70 leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Languages */}
        <section id="languages" className="mx-auto max-w-6xl px-4 sm:px-8 pb-20 sm:pb-28 scroll-mt-20">
          <div className="flex items-center gap-2 mb-8">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Speaks your language</span>
          </div>
          <p className="text-sm sm:text-base text-ink/70 leading-relaxed max-w-2xl mb-8">
            Scan results come back in the same language you scanned in — no translation gap between
            what a scammer wrote and what you understand.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {LANGUAGES.map((lang) => (
              <div
                key={lang}
                className="relative border border-ink bg-paper/60 px-4 py-3 text-center text-sm font-bold"
              >
                <CornerBrackets />
                {lang}
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-6xl px-4 sm:px-8 pb-20 sm:pb-28 scroll-mt-20">
          <div className="flex items-center gap-2 mb-8">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">How it works</span>
          </div>
          <div className="grid gap-6 sm:grid-cols-3">
            {STEPS.map((s) => (
              <div key={s.n}>
                <span className="text-4xl font-extrabold text-accent">{s.n}</span>
                <h3 className="mt-2 text-sm font-bold uppercase tracking-[0.1em]">{s.title}</h3>
                <p className="mt-2 text-[13px] text-ink/70 leading-relaxed">{s.body}</p>
              </div>
            ))}
          </div>
          <Link
            to="/login"
            className="mt-10 inline-block bg-accent px-6 py-3 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors"
          >
            Try it now
          </Link>
        </section>

        {/* Free stack */}
        <section id="stack" className="mx-auto max-w-6xl px-4 sm:px-8 pb-20 sm:pb-28 scroll-mt-20">
          <div className="flex items-center gap-2 mb-8">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Built free, forever</span>
          </div>
          <p className="text-sm sm:text-base text-ink/70 leading-relaxed max-w-2xl mb-8">
            Every layer runs on a free tier — no card, no hidden cost, nothing that breaks at scale
            without a plan to pay for it.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {STACK.map((s) => (
              <div key={s.name} className="relative border border-ink bg-paper/60 p-4">
                <CornerBrackets />
                <p className="text-sm font-bold">{s.name}</p>
                <p className="mt-1 text-[11px] text-ink/60">{s.role}</p>
              </div>
            ))}
          </div>
        </section>
      </main>

      <footer className="border-t border-ink px-4 py-6 sm:px-8 text-[11px] text-ink/50">
        Built for The Maverick Effect AI Challenge — free to use, always.
      </footer>
    </div>
  )
}
