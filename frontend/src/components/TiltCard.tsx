import { useRef, useState, type ReactNode, type PointerEvent } from 'react'

/** Pure-CSS 3D tilt on pointer move — perspective + rotateX/Y follow the
 * cursor, with a light glare layer for depth. No 3D library, keeps the
 * bundle light. Falls back to a flat card on touch devices (no pointer move). */
export function TiltCard({ children, className = '' }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [style, setStyle] = useState<{ transform: string; glareX: number; glareY: number }>({
    transform: 'perspective(900px) rotateX(0deg) rotateY(0deg)',
    glareX: 50,
    glareY: 50,
  })

  const handleMove = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const px = (e.clientX - rect.left) / rect.width
    const py = (e.clientY - rect.top) / rect.height
    const rotateY = (px - 0.5) * 14
    const rotateX = (0.5 - py) * 14
    setStyle({
      transform: `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02,1.02,1.02)`,
      glareX: px * 100,
      glareY: py * 100,
    })
  }

  const handleLeave = () => {
    setStyle({ transform: 'perspective(900px) rotateX(0deg) rotateY(0deg)', glareX: 50, glareY: 50 })
  }

  return (
    <div
      ref={ref}
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
      style={{ transform: style.transform, transition: 'transform 150ms ease-out' }}
      className={`relative will-change-transform ${className}`}
    >
      {children}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-0 hover:opacity-100 transition-opacity"
        style={{
          background: `radial-gradient(circle at ${style.glareX}% ${style.glareY}%, rgba(255,255,255,0.35), transparent 60%)`,
        }}
      />
    </div>
  )
}
