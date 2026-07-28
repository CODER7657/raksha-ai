import { CornerBrackets } from '../components/CornerBrackets'

const PIPELINE_STEPS = [
  {
    n: '01',
    title: 'Offline rule-check',
    body: 'An instant, zero-network keyword/pattern check catches obvious scams first — matters most for low-bandwidth users.',
  },
  {
    n: '02',
    title: 'Local embedding',
    body: 'Your message is embedded on the server using a free multilingual model — no external API call for this step.',
  },
  {
    n: '03',
    title: 'Retrieve similar scams',
    body: 'A vector similarity search against a real database of known scam patterns pulls back the closest matches.',
  },
  {
    n: '04',
    title: 'Grounded classification',
    body: 'An LLM (Groq, with Gemini as fallback) judges your actual message — using the retrieved patterns as reference context, not a raw guess.',
  },
  {
    n: '05',
    title: 'Plain-language result',
    body: 'Risk score, verdict, the exact flagged phrases, why it matters, and one clear next step — saved only to your own scan history.',
  },
]

const SECURITY_POINTS = [
  'Every request is verified server-side against the signed JWT — the backend never trusts a client-supplied identity.',
  'Row Level Security on every data table — the database itself blocks a user from ever reading another user’s scan history, not just the application code.',
  'The service role key never leaves the backend; the frontend only ever holds the public anon key, which is safe by design.',
  'Rate limiting protects the shared free LLM quota from abuse.',
  'If both LLM providers are ever down, the offline rule-engine still returns a conservative result instead of a bare error.',
]

const STACK = [
  { name: 'Groq + Gemini', role: 'primary / fallback LLM, both free tier' },
  { name: 'Supabase', role: 'Postgres, pgvector, Auth, Row Level Security' },
  { name: 'faster-whisper', role: 'local speech-to-text for voice/call scans' },
  { name: 'FastAPI', role: 'backend API, deployed on Render' },
  { name: 'React + Vite + Tailwind', role: 'frontend, deployed on Vercel' },
  { name: 'GitHub Actions', role: 'CI on every pull request' },
]

function SectionHeading({ children }: { children: string }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      <span className="h-2 w-2 bg-accent" aria-hidden="true" />
      <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">{children}</span>
    </div>
  )
}

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl flex flex-col gap-10">
      <div>
        <SectionHeading>About Raksha AI</SectionHeading>
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <p className="text-sm text-ink leading-relaxed">
            Raksha AI helps first-time digital banking users in India check a suspicious SMS, WhatsApp
            message, UPI request, or call snippet — in their own language — before it costs them money.
            Built for the Maverick Effect AI Challenge.
          </p>
        </div>
      </div>

      <div>
        <SectionHeading>How a scan works</SectionHeading>
        <div className="flex flex-col gap-4">
          {PIPELINE_STEPS.map((step) => (
            <div key={step.n} className="relative border border-ink bg-paper/60 backdrop-blur-sm p-5 flex gap-4">
              <CornerBrackets />
              <span className="shrink-0 text-2xl font-extrabold text-accent">{step.n}</span>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-[0.1em] text-ink">{step.title}</h3>
                <p className="mt-1 text-sm text-ink/70 leading-relaxed">{step.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHeading>Security &amp; privacy</SectionHeading>
        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />
          <ul className="flex flex-col gap-3">
            {SECURITY_POINTS.map((point, i) => (
              <li key={i} className="flex gap-3 text-sm text-ink/80 leading-relaxed">
                <span className="shrink-0 text-accent">■</span>
                {point}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div>
        <SectionHeading>Built on a free stack</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2">
          {STACK.map((s) => (
            <div key={s.name} className="relative border border-ink bg-paper/60 p-4">
              <CornerBrackets />
              <p className="text-sm font-bold text-ink">{s.name}</p>
              <p className="mt-1 text-[11px] text-ink/60">{s.role}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
