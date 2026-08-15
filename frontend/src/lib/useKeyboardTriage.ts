import { useEffect, useRef } from 'react'

/** Keyboard triage, shared by the pattern-draft queue (#32 A) and the evasion
 * queue (#41 §3).
 *
 * Extracted rather than copied. Two queues with two key handlers drift, and the
 * drift is silent: a reviewer who learns `U` undoes on one screen and finds it
 * does nothing on the other stops trusting the keyboard and reaches for the
 * mouse — which is the throughput this is meant to protect.
 */
export function useKeyboardTriage(opts: {
  enabled: boolean
  choosingReason: boolean
  /** The reason list this queue actually displays.
   *
   * Not defaulted silently to one queue's list. The hook matched the pattern
   * queue's `REJECTION_REASONS` while the evasion queue rendered its own, so
   * pressing the key labelled "this strategy is producing noise" recorded
   * "wrong language or script". Rejections are training data for whoever tunes
   * the agent; a reason that does not match the key the reviewer pressed is
   * worse than no reason at all. Required, so a new queue cannot forget it. */
  reasons: readonly { key: string; code: string; label: string }[]
  onAccept: () => void
  onRejectStart: () => void
  onRejectCancel: () => void
  onReason: (code: string, label: string) => void
  onSkip: () => void
  onUndo: () => void
}) {
  const ref = useRef(opts)
  ref.current = opts

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const o = ref.current
      if (!o.enabled) return
      // Modified keys belong to the browser and the OS.
      if (event.metaKey || event.ctrlKey || event.altKey) return

      const target = event.target as HTMLElement | null
      if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) {
        return
      }

      const key = event.key.toLowerCase()

      if (o.choosingReason) {
        if (key === 'escape') {
          event.preventDefault()
          o.onRejectCancel()
          return
        }
        const reason = o.reasons.find((r) => r.key === event.key)
        if (reason) {
          event.preventDefault()
          o.onReason(reason.code, reason.label)
        }
        return
      }

      if (key === 'a') {
        event.preventDefault()
        o.onAccept()
      } else if (key === 'r') {
        event.preventDefault()
        o.onRejectStart()
      } else if (key === 's') {
        event.preventDefault()
        o.onSkip()
      } else if (key === 'u') {
        event.preventDefault()
        o.onUndo()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
