import { useRef, useState, type ReactNode, type PointerEvent } from 'react'

/** Gentle 3D tilt that follows a mouse pointer.
 *
 * Motion is opt-in: it only runs when the system reports
 * `prefers-reduced-motion: no-preference`, and only for a mouse (touch never
 * tilts). No glare layer — the Swiss system has no gradients or shadows. */
function motionAllowed() {
  return typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: no-preference)').matches
}

const FLAT = 'perspective(900px) rotateX(0deg) rotateY(0deg)'

export function TiltCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [transform, setTransform] = useState(FLAT)

  const handleMove = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' || !ref.current || !motionAllowed()) return
    const rect = ref.current.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width
    const py = (e.clientY - rect.top) / rect.height
    setTransform(`perspective(900px) rotateX(${(0.5 - py) * 10}deg) rotateY(${(px - 0.5) * 10}deg)`)
  }

  return (
    <div
      ref={ref}
      onPointerMove={handleMove}
      onPointerLeave={() => setTransform(FLAT)}
      style={{ transform }}
      className={`relative motion-safe:transition-transform motion-safe:duration-150 motion-safe:ease-out ${className}`}
    >
      {children}
    </div>
  )
}
