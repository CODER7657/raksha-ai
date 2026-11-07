import { REJECTION_REASONS } from '../lib/review'

export function Key({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="border border-ink px-1 font-mono text-xs font-bold text-ink">{children}</kbd>
  )
}

export function Shortcuts({
  choosingReason,
  reasons = REJECTION_REASONS,
}: {
  choosingReason: boolean
  reasons?: readonly { key: string; code: string; label: string }[]
}) {
  return (
    <div className="border border-line bg-white px-3 py-2 mb-4 text-xs text-ink/60 flex flex-wrap gap-x-4 gap-y-1">
      {choosingReason ? (
        <>
          <span className="text-ink font-bold">Why reject?</span>
          {reasons.map((r) => (
            <span key={r.code}>
              <Key>{r.key}</Key> {r.label}
            </span>
          ))}
          <span>
            <Key>Esc</Key> cancel
          </span>
        </>
      ) : (
        <>
          <span>
            <Key>A</Key> accept
          </span>
          <span>
            <Key>R</Key> reject
          </span>
          <span>
            <Key>S</Key> skip
          </span>
          <span>
            <Key>U</Key> undo
          </span>
        </>
      )}
    </div>
  )
}
