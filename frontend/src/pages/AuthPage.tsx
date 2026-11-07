import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { SWISS_CONTAINER } from '../components/SwissGrid'

type Mode = 'login' | 'signup' | 'forgot'

function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <path fill="#EA4335" d="M12 10.2v3.9h5.5c-.24 1.3-1.7 3.8-5.5 3.8-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.1.8 3.8 1.5l2.6-2.5C16.9 3.3 14.7 2.3 12 2.3 6.9 2.3 2.7 6.6 2.7 11.7S6.9 21.2 12 21.2c6.9 0 9.4-4.9 9.4-7.4 0-.5 0-.9-.1-1.3H12Z" />
    </svg>
  )
}

const COPY: Record<Mode, string> = {
  login: 'Log in to scan a message or call for scams.',
  signup: 'Create an account to start scanning for scams.',
  forgot: "Enter your email and we'll send a reset link.",
}

export function AuthPage() {
  const { user, loading, signInWithPassword, signUpWithPassword, signInWithGoogle, resetPasswordForEmail } = useAuth()
  const navigate = useNavigate()

  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  useEffect(() => {
    if (!loading && user) navigate('/app', { replace: true })
  }, [loading, user, navigate])

  const switchMode = (m: Mode) => {
    setMode(m)
    setError('')
    setInfo('')
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setSubmitting(true)
    try {
      if (mode === 'login') {
        await signInWithPassword(email, password)
      } else if (mode === 'signup') {
        await signUpWithPassword(email, password)
        setInfo('Account created — check your email to confirm before logging in.')
      } else {
        await resetPasswordForEmail(email)
        setInfo('Reset link sent — check your email.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSubmitting(false)
    }
  }

  const handleGoogle = async () => {
    setError('')
    try {
      await signInWithGoogle()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed')
    }
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <div className={`${SWISS_CONTAINER} grid grid-cols-12 gap-x-4 gap-y-8 py-10 sm:gap-x-6 sm:py-16`}>
        <div className="col-span-12 md:col-span-5">
          <p className="swiss-label flex items-center gap-2 text-ink">
            <span className="h-2 w-2 bg-accent" aria-hidden="true" />
            Raksha AI · Secure Access
          </p>
          <ShieldCheck aria-hidden="true" size={32} strokeWidth={1.75} className="mt-8 text-accent" />
          <h1 className="swiss-display mt-4 text-[clamp(2.5rem,9vw,4.5rem)]">Raksha AI</h1>
          <p className="mt-4 max-w-sm text-base leading-relaxed text-ink">{COPY[mode]}</p>
        </div>

        <div className="col-span-12 border-t-2 border-rule pt-6 md:col-span-6 md:col-start-7 lg:col-span-5 lg:col-start-8">
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <label className="flex flex-col gap-2">
              <span className="swiss-label text-ink">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="min-h-11 border-2 border-ink bg-paper px-3 py-2 text-base text-ink placeholder:text-ink/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                placeholder="you@example.com"
              />
            </label>

            {mode !== 'forgot' && (
              <label className="flex flex-col gap-2">
                <span className="swiss-label text-ink">Password</span>
                <input
                  type="password"
                  required
                  minLength={6}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="min-h-11 border-2 border-ink bg-paper px-3 py-2 text-base text-ink placeholder:text-ink/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  placeholder="••••••••"
                />
              </label>
            )}

            {mode === 'login' && (
              <button
                type="button"
                onClick={() => switchMode('forgot')}
                className="min-h-11 self-start text-sm text-ink underline underline-offset-4 hover:text-accent"
              >
                Forgot password?
              </button>
            )}

            {error && (
              <p role="alert" className="border-l-4 border-accent py-2 pl-4 text-sm text-accent-dark">{error}</p>
            )}
            {info && (
              <p role="status" className="border-l-4 border-ink py-2 pl-4 text-sm text-ink">{info}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 min-h-12 bg-accent px-5 py-3 text-left text-sm font-bold uppercase tracking-[0.08em] text-accent-ink transition-colors hover:bg-ink disabled:opacity-60"
            >
              {submitting
                ? 'Please wait…'
                : mode === 'login'
                  ? 'Log in'
                  : mode === 'signup'
                    ? 'Sign up'
                    : 'Send reset link'}
            </button>
          </form>

          {mode !== 'forgot' && (
            <>
              <div className="flex items-center gap-3 my-5">
                <div className="h-px flex-1 bg-line" />
                <span className="text-xs uppercase tracking-[0.08em] text-ink/70">or</span>
                <div className="h-px flex-1 bg-line" />
              </div>

              <button
                type="button"
                onClick={handleGoogle}
                className="flex min-h-12 w-full items-center gap-3 border-2 border-ink px-5 py-3 text-sm font-bold uppercase tracking-[0.06em] text-ink transition-colors hover:bg-ink hover:text-paper"
              >
                <GoogleMark />
                Continue with Google
              </button>
            </>
          )}

          <p className="mt-6 text-sm text-ink/70">
            {mode === 'login' && (
              <>
                New here?{' '}
                <button type="button" className="min-h-11 font-bold text-ink underline underline-offset-4 hover:text-accent" onClick={() => switchMode('signup')}>
                  Sign up
                </button>
              </>
            )}
            {(mode === 'signup' || mode === 'forgot') && (
              <>
                Already have an account?{' '}
                <button type="button" className="min-h-11 font-bold text-ink underline underline-offset-4 hover:text-accent" onClick={() => switchMode('login')}>
                  Log in
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
