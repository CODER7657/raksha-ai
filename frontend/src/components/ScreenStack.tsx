import { CornerBrackets } from './CornerBrackets'

/** Three depth-offset mockup "app screens" behind the hero visual, each
 * with skeleton content bars — the front one has a scanline sweeping
 * through it to sell the "actively scanning" idea. Pure CSS, no images. */
function MockScreen({ scanning = false, className = '' }: { scanning?: boolean; className?: string }) {
  return (
    <div className={`relative border border-ink bg-paper overflow-hidden ${className}`}>
      {scanning && <CornerBrackets />}

      <div className="flex items-center gap-1.5 border-b border-line px-3 py-2">
        <span className="h-1.5 w-1.5 rounded-full bg-ink/20" />
        <span className="h-1.5 w-1.5 rounded-full bg-ink/20" />
        <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      </div>

      <div className="p-4 flex flex-col gap-2.5">
        <div className="h-2 w-2/3 bg-ink/15 bar-pulse" />
        <div className="h-2 w-full bg-ink/10 bar-pulse" style={{ animationDelay: '0.3s' }} />
        <div className="h-2 w-5/6 bg-ink/10 bar-pulse" style={{ animationDelay: '0.6s' }} />
        <div className="mt-2 h-6 w-1/3 bg-accent/70" />
      </div>

      {scanning && (
        <div
          className="scanline pointer-events-none absolute left-0 right-0 h-6"
          style={{
            background: 'linear-gradient(to bottom, transparent, rgba(255,90,31,0.25), transparent)',
          }}
        />
      )}
    </div>
  )
}

export function ScreenStack() {
  return (
    <div className="relative h-full w-full">
      <MockScreen className="absolute inset-x-6 top-6 bottom-0 rotate-[-4deg] opacity-60" />
      <MockScreen className="absolute inset-x-3 top-3 bottom-0 rotate-[2deg] opacity-80" />
      <MockScreen scanning className="absolute inset-0" />
    </div>
  )
}
