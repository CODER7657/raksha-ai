import { useTranslation } from 'react-i18next'

const PIPELINE_STEPS = [
  { n: '01', titleKey: 'about.pipeline1Title', bodyKey: 'about.pipeline1Body' },
  { n: '02', titleKey: 'about.pipeline2Title', bodyKey: 'about.pipeline2Body' },
  { n: '03', titleKey: 'about.pipeline3Title', bodyKey: 'about.pipeline3Body' },
  { n: '04', titleKey: 'about.pipeline4Title', bodyKey: 'about.pipeline4Body' },
  { n: '05', titleKey: 'about.pipeline5Title', bodyKey: 'about.pipeline5Body' },
]

const SECURITY_KEYS = ['about.security1', 'about.security2', 'about.security3', 'about.security4', 'about.security5']

const STACK = [
  { name: 'Groq + Gemini', roleKey: 'about.stackGroqGemini' },
  { name: 'Supabase', roleKey: 'about.stackSupabase' },
  { name: 'Sarvam · Groq Whisper', roleKey: 'about.stackWhisper' },
  { name: 'FastAPI', roleKey: 'about.stackFastapi' },
  { name: 'React + Vite + Tailwind', roleKey: 'about.stackFrontend' },
  { name: 'GitHub Actions', roleKey: 'about.stackGithub' },
]

function SectionHeading({ children }: { children: string }) {
  return (
    <div className="flex items-center gap-2 mb-6">
      <span className="h-2 w-2 bg-accent" aria-hidden="true" />
      <span className="swiss-label text-ink">{children}</span>
    </div>
  )
}

export function AboutPage() {
  const { t } = useTranslation()

  return (
    <div className="max-w-3xl flex flex-col gap-10">
      <div>
        <SectionHeading>{t('about.eyebrowAbout')}</SectionHeading>
        <div className="border-t-2 border-rule pt-6">
          <p className="text-sm text-ink leading-relaxed">{t('about.intro')}</p>
        </div>
      </div>

      <div>
        <SectionHeading>{t('about.eyebrowHowItWorks')}</SectionHeading>
        <div className="flex flex-col gap-4">
          {PIPELINE_STEPS.map((step) => (
            <div key={step.n} className="border-t-2 border-rule pt-5 flex gap-4">
              <span className="shrink-0 text-2xl font-extrabold text-accent">{step.n}</span>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-[0.1em] text-ink">{t(step.titleKey)}</h3>
                <p className="mt-1 text-sm text-ink/70 leading-relaxed">{t(step.bodyKey)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div>
        <SectionHeading>{t('about.eyebrowSecurity')}</SectionHeading>
        <div className="border-t-2 border-rule pt-6">
          <ul className="flex flex-col gap-3">
            {SECURITY_KEYS.map((key) => (
              <li key={key} className="flex gap-3 text-sm text-ink/80 leading-relaxed">
                <span className="mt-2 h-2 w-2 shrink-0 bg-accent" aria-hidden="true" />
                {t(key)}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div>
        <SectionHeading>{t('about.eyebrowStack')}</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2">
          {STACK.map((s) => (
            <div key={s.name} className="border-t border-rule pt-4">
              <p className="text-sm font-bold text-ink">{s.name}</p>
              <p className="mt-1 text-xs text-ink/60">{t(s.roleKey)}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
