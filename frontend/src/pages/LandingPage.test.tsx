import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import '../i18n'
import { LandingPage } from './LandingPage'

vi.mock('../lib/supabaseClient', () => ({ supabase: {} }))

afterEach(cleanup)

function renderLanding() {
  return render(
    <MemoryRouter>
      <LandingPage />
    </MemoryRouter>,
  )
}

describe('hero language claim', () => {
  it('qualifies the 12 with how many languages are speaker-reviewed', () => {
    renderLanding()
    expect(screen.getByText('Languages checked')).toBeTruthy()
    expect(screen.getByText('3 speaker-reviewed: English, Hindi, Gujarati')).toBeTruthy()
  })

  it('never states a bare "Indian languages" coverage claim', () => {
    renderLanding()
    expect(screen.queryByText('Indian languages')).toBeNull()
  })
})
