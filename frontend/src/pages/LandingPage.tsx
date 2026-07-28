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
      <header className="flex items-center justify-between border-b border-ink px-4 py-4 sm:px-8 sm:py-5 bg-paper/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 bg-accent" aria-hidden="true" />
          <span className="text-base font-extrabold uppercase tracking-tight">Raksha AI</span>
        </div>
        <Link
          to="/login"
          className="border border-ink px-4 py-2 text-[11px] font-bold uppercase tracking-[0.15em] hover:bg-ink hover:text-white transition-colors"
        >
          Log in
        </Link>
      </header>

      <main>
        {/* Hero — bordered grid-block layout: eyebrow row / headline row /
            content row, each divided by full-width grid lines so blocks
            align exactly to the shared .grid-bg, matching the reference
            "blocky" composition instead of floating cards. */}
        <section className="border-b border-ink">
          <div className="flex items-center gap-2 border-b border-ink px-4 sm:px-8 py-2.5">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            <span className="text-[10px] tracking-[0.2em] uppercase text-ink/60">
              Maverick Effect AI Challenge
            </span>
          </div>

          <div className="relative border-b border-ink px-4 sm:px-8 py-6 sm:py-8">
            <span className="absolute top-2 left-2 h-1.5 w-1.5 bg-accent" aria-hidden="true" />
            <span className="absolute top-2 right-2 h-1.5 w-1.5 bg-accent" aria-hidden="true" />
            <h1 className="text-4xl sm:text-6xl lg:text-7xl font-extrabold uppercase tracking-tight leading-[0.92]">
              Spot the scam
              <br />
              before it costs you
            </h1>
          </div>

          <div className="grid md:grid-cols-[1.1fr_1fr_auto] divide-y divide-ink md:divide-y-0 md:divide-x">
            <div className="px-4 sm:px-8 py-6 flex flex-col justify-center gap-5">
              <p className="text-sm sm:text-base text-ink/70 leading-relaxed">
                Paste a message, a UPI request, or a call recording. Checked against real scam
                patterns — retrieved from a live database, not guessed — with a plain-language
                explanation in your own language.
              </p>
              <div className="flex flex-wrap gap-3">
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
              <div className="flex gap-6 flex-wrap">
                {STATS.map((s) => (
                  <div key={s.label}>
                    <p className="text-lg font-extrabold text-accent">{s.value}</p>
                    <p className="text-[9px] uppercase tracking-[0.15em] text-ink/50">{s.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Primary hero visual: the robot, centered, enlarged, tilts with
                the pointer while its eyes independently track the cursor
                anywhere on the page. */}
            <div className="flex items-center justify-center py-8 md:py-0">
              <TiltCard className="[transform-style:preserve-3d]">
                <div className="scale-125 sm:scale-150">
                  <RobotWatcher />
                </div>
              </TiltCard>
            </div>

            {/* Small bordered accent cell, mirrors the compact image block
                in the reference layout. */}
            <div className="hidden md:block w-36 lg:w-44 p-3">
              <div className="relative h-full">
                <TiltCard className="h-full">
                  <div className="h-full">
                    <ScreenStack />
                  </div>
                </TiltCard>
              </div>
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
