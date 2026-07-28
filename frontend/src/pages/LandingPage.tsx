import { Link } from 'react-router-dom'
import { TiltCard } from '../components/TiltCard'
import { CornerBrackets } from '../components/CornerBrackets'
import { ScreenStack } from '../components/ScreenStack'
import { RobotWatcher } from '../components/RobotWatcher'

const STATS = [
  { value: '12', label: 'Indian languages' },
  { value: '0₹', label: 'to use, always' },
  { value: '<5s', label: 'per scan' },
]

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

export function LandingPage() {
  return (
    <div className="grid-bg min-h-screen font-mono text-ink">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3 sm:px-8 bg-paper/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-sm font-extrabold uppercase tracking-tight">Raksha AI</span>
        </div>
        <Link
          to="/login"
          className="border border-ink px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.15em] hover:bg-ink hover:text-white transition-colors"
        >
          Log in
        </Link>
      </header>

      <main>
        {/* Hero */}
        <section className="mx-auto max-w-6xl px-4 sm:px-8 py-20 sm:py-32 grid gap-14 md:grid-cols-2 md:items-center">
          <div>
            <div className="flex items-center gap-2 mb-5">
              <span className="h-2 w-2 bg-accent" aria-hidden="true" />
              <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">
                Maverick Effect AI Challenge
              </span>
            </div>
            <h1 className="text-5xl sm:text-7xl font-extrabold uppercase tracking-tight leading-[0.92]">
              Spot the scam
              <br />
              before it costs you
            </h1>
            <p className="mt-6 text-base sm:text-lg text-ink/70 leading-relaxed max-w-lg">
              Paste a message, a UPI request, or a call recording. Raksha AI checks it against real
              scam patterns — retrieved from a live database, not guessed — and tells you, in your
              own language, exactly what to do next. Free, always, built for people who never asked
              for this problem in the first place.
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

            <div className="mt-10 flex gap-8 flex-wrap">
              {STATS.map((s) => (
                <div key={s.label}>
                  <p className="text-2xl font-extrabold text-accent">{s.value}</p>
                  <p className="text-[10px] uppercase tracking-[0.15em] text-ink/50">{s.label}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Hero visual: layered "app screens" (scanline + skeleton bars) with
              a full 3D pointer-tilt, plus a robot badge whose eyes track the
              cursor anywhere on the page. */}
          <div className="relative mx-auto w-full max-w-sm">
            <TiltCard className="aspect-[4/5] w-full [transform-style:preserve-3d]">
              <ScreenStack />
            </TiltCard>
            <div className="absolute -bottom-6 -left-6 hidden sm:block">
              <RobotWatcher />
            </div>
          </div>
        </section>

        {/* Feature grid */}
        <section className="mx-auto max-w-6xl px-4 sm:px-8 pb-16 sm:pb-24">
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

        {/* How it works */}
        <section id="how-it-works" className="mx-auto max-w-6xl px-4 sm:px-8 pb-16 sm:pb-24 scroll-mt-20">
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
      </main>

      <footer className="border-t border-ink px-4 py-6 sm:px-8 text-[11px] text-ink/50">
        Built for The Maverick Effect AI Challenge — free to use, always.
      </footer>
    </div>
  )
}
