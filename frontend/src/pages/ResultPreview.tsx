import { useLocation, useNavigate } from 'react-router-dom'
import { CornerBrackets } from '../components/CornerBrackets'

/** Temporary raw view of the scan response until the real Result/Risk Report screen is built. */
export function ResultPreview() {
  const location = useLocation()
  const navigate = useNavigate()
  const result = (location.state as { result?: unknown } | null)?.result

  if (!result) {
    return (
      <div className="mx-auto max-w-2xl text-center">
        <p className="text-sm text-ink/60 mb-4">No scan result to show.</p>
        <button
          onClick={() => navigate('/')}
          className="border border-ink px-4 py-2 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
        >
          Back to scan
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex items-center gap-2 mb-6">
        <span className="h-2 w-2 bg-accent" aria-hidden="true" />
        <span className="text-[11px] tracking-[0.2em] uppercase text-ink/60">Scan result (preview)</span>
      </div>
      <div className="relative border border-ink bg-paper/60 backdrop-blur-sm p-6 sm:p-8">
        <CornerBrackets />
        <pre className="text-xs text-ink whitespace-pre-wrap break-words">{JSON.stringify(result, null, 2)}</pre>
      </div>
      <button
        onClick={() => navigate('/')}
        className="mt-4 border border-ink px-4 py-2 text-xs font-bold uppercase tracking-[0.15em] text-ink hover:bg-ink hover:text-white transition-colors"
      >
        Scan another
      </button>
    </div>
  )
}
