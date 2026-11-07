/** The visible 12-column grid behind the landing and result pages.
 *
 * Absolutely positioned: render it as the first child of a `relative`
 * full-page wrapper so it runs the whole height of the page.
 *
 * Drawn with real elements on the same container and gutters the content
 * uses (`SWISS_CONTAINER`, `grid-cols-12 gap-x-4 sm:gap-x-6`), so a block that
 * spans columns 1-7 actually starts and stops on a line. Hairlines in the
 * `line` token: visible on white, decorative, never carrying meaning. */
export const SWISS_CONTAINER = 'mx-auto w-full max-w-6xl px-4 sm:px-8'

export const GRID_COLUMNS = 12

export function SwissGrid() {
  return (
    <div aria-hidden="true" data-testid="swiss-grid" className="pointer-events-none absolute inset-0 z-0">
      <div className={`${SWISS_CONTAINER} grid h-full grid-cols-12 gap-x-4 sm:gap-x-6`}>
        {Array.from({ length: GRID_COLUMNS }, (_, i) => (
          <div key={i} className={`h-full border-l border-line ${i === GRID_COLUMNS - 1 ? 'border-r' : ''}`} />
        ))}
      </div>
    </div>
  )
}
