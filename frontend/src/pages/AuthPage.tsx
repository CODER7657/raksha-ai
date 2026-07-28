import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { CornerBrackets } from '../components/CornerBrackets'

type Mode = 'login' | 'signup' | 'forgot'

function ShieldMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-6 w-6 text-ink" fill="none" aria-hidden="true">
      <path
        d="M12 2 4 5v6c0 5 3.4 8.7 8 9 4.6-.3 8-4 8-9V5l-8-3Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="m8.5 12 2.5 2.5L15.5 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

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
    <div className="grid-bg min-h-screen flex items-center justify-center px-4 py-10 font-mono">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-6">
          <span className="h-2 w-2 bg-accent" aria-hidden="true" />
          <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Raksha AI · Secure Access</span>
        </div>

        <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
          <CornerBrackets />

          <div className="flex flex-col items-start mb-6">
            <ShieldMark />
            <h1 className="mt-3 text-2xl font-extrabold uppercase tracking-tight text-ink">Raksha AI</h1>
            <p className="mt-2 text-xs text-ink/60 leading-relaxed">{COPY[mode]}</p>
          </div>

          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <label className="flex flex-col gap-1.5 text-left">
              <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="border border-ink bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent"
                placeholder="you@example.com"
              />
            </label>

            {mode !== 'forgot' && (
              <label className="flex flex-col gap-1.5 text-left">
                <span className="text-[10px] font-bold uppercase tracking-[0.15em] text-ink/70">Password</span>
                <input
                  type="password"
                  required
                  minLength={6}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="border border-ink bg-white px-3 py-2 text-sm text-ink placeholder:text-ink/30 focus:outline-none focus:ring-2 focus:ring-accent"
                  placeholder="••••••••"
                />
              </label>
            )}

            {mode === 'login' && (
              <button
                type="button"
                onClick={() => switchMode('forgot')}
                className="self-end text-[10px] uppercase tracking-wider text-ink/50 hover:text-accent"
              >
                Forgot password?
              </button>
            )}

            {error && (
              <p className="border border-red-600 bg-red-50 px-3 py-2 text-[11px] text-red-700">{error}</p>
            )}
            {info && (
              <p className="border border-accent bg-orange-50 px-3 py-2 text-[11px] text-ink">{info}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="mt-1 bg-accent px-4 py-2.5 text-xs font-bold uppercase tracking-[0.15em] text-accent-ink hover:bg-ink transition-colors disabled:opacity-50"
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
                <span className="text-[10px] uppercase tracking-widest text-ink/40">or</span>
                <div className="h-px flex-1 bg-line" />
              </div>

              <button
                type="button"
                onClick={handleGoogle}
                className="w-full flex items-center justify-center gap-2 border border-ink py-2.5 text-xs font-bold uppercase tracking-[0.1em] text-ink hover:bg-ink hover:text-white transition-colors"
              >
                <GoogleMark />
                Continue with Google
              </button>
            </>
          )}

          <p className="mt-6 text-center text-[11px] text-ink/60">
            {mode === 'login' && (
              <>
                New here?{' '}
                <button type="button" className="font-bold text-ink underline underline-offset-2" onClick={() => switchMode('signup')}>
                  Sign up
                </button>
              </>
            )}
            {(mode === 'signup' || mode === 'forgot') && (
              <>
                Already have an account?{' '}
                <button type="button" className="font-bold text-ink underline underline-offset-2" onClick={() => switchMode('login')}>
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
