import { useEffect, useRef } from 'react'

/** A small robot face whose eyes track the mouse anywhere on the page —
 * classic "eyes follow cursor" trick, done with plain CSS transforms (no
 * canvas/3D library). Reinforces the "always watching for scams" idea. */
export function RobotWatcher() {
  const leftPupilRef = useRef<HTMLSpanElement>(null)
  const rightPupilRef = useRef<HTMLSpanElement>(null)
  const faceRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const maxOffset = 3.5 // px the pupil can travel from eye center

    const handleMove = (e: PointerEvent) => {
      const eyes = [leftPupilRef.current, rightPupilRef.current]
      for (const pupil of eyes) {
        if (!pupil) continue
        const socket = pupil.parentElement
        if (!socket) continue
        const rect = socket.getBoundingClientRect()
        const cx = rect.left + rect.width / 2
        const cy = rect.top + rect.height / 2
        const angle = Math.atan2(e.clientY - cy, e.clientX - cx)
        const dx = Math.cos(angle) * maxOffset
        const dy = Math.sin(angle) * maxOffset
        pupil.style.transform = `translate(${dx}px, ${dy}px)`
      }
    }

    window.addEventListener('pointermove', handleMove)
    return () => window.removeEventListener('pointermove', handleMove)
  }, [])

  return (
    <div
      ref={faceRef}
      className="relative border border-ink bg-ink px-5 py-4 flex flex-col items-center gap-3 w-fit"
      aria-hidden="true"
    >
      <span className="absolute -top-3 left-1/2 -translate-x-1/2 h-3 w-0.5 bg-ink/60" />
      <span className="absolute -top-4 left-1/2 -translate-x-1/2 h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />

      <div className="flex gap-3">
        {[leftPupilRef, rightPupilRef].map((ref, i) => (
          <span
            key={i}
            className="relative h-5 w-5 rounded-full bg-paper flex items-center justify-center overflow-hidden"
          >
            <span
              ref={ref}
              className="h-2 w-2 rounded-full bg-ink transition-transform duration-75 ease-out"
            />
          </span>
        ))}
      </div>

      <span className="h-1 w-8 rounded-full bg-paper/30" />
    </div>
  )
}
