import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { GRID_COLUMNS, SwissGrid, SWISS_CONTAINER } from './SwissGrid'

afterEach(cleanup)

describe('SwissGrid', () => {
  it('draws exactly twelve column lines', () => {
    render(<SwissGrid />)
    const grid = screen.getByTestId('swiss-grid')
    const columns = grid.firstElementChild!.children
    expect(GRID_COLUMNS).toBe(12)
    expect(columns).toHaveLength(12)
    for (const column of Array.from(columns)) expect(column.className).toContain('border-l')
    // Only the last column closes the grid on the right.
    expect(columns[11].className).toContain('border-r')
    expect(columns[0].className).not.toContain('border-r')
  })

  it('is decorative: hidden from assistive tech and never intercepts a tap', () => {
    render(<SwissGrid />)
    const grid = screen.getByTestId('swiss-grid')
    expect(grid.getAttribute('aria-hidden')).toBe('true')
    expect(grid.className).toContain('pointer-events-none')
    expect(grid.textContent).toBe('')
  })

  it('shares its container with the page content so columns line up', () => {
    render(<SwissGrid />)
    const inner = screen.getByTestId('swiss-grid').firstElementChild!
    for (const cls of SWISS_CONTAINER.split(' ')) expect(inner.className.split(/\s+/)).toContain(cls)
    expect(inner.className).toContain('grid-cols-12')
  })
})
