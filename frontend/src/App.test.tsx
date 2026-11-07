import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import i18n from './i18n'
import App from './App'

// No network and no Supabase in unit tests: a logged-out visitor, a client stub.
const auth = vi.hoisted(() => ({ user: null as null | { id: string }, loading: false }))
vi.mock('./context/AuthContext', () => ({ useAuth: () => auth }))
vi.mock('./lib/supabaseClient', () => ({ supabase: {} }))

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

afterEach(async () => {
  cleanup()
  auth.user = null
  auth.loading = false
  await i18n.changeLanguage('en')
})

describe('unknown routes', () => {
  it.each(['/nope', '/app/does-not-exist', '/login/extra', '/deeply/nested/missing/path'])(
    'renders the 404 page for %s instead of a blank screen',
    (path) => {
      const { container } = renderAt(path)
      expect(container.textContent?.trim()).not.toBe('')
      expect(screen.getByRole('heading', { level: 1, name: 'Page not found' })).toBeTruthy()
      expect(screen.getByText(path)).toBeTruthy()
    },
  )

  it('links back to the home page', () => {
    renderAt('/nope')
    const link = screen.getByRole('link', { name: 'Go to home page' })
    expect(link.getAttribute('href')).toBe('/')
  })

  it('shows the unknown path as text, never as markup', () => {
    renderAt('/%3Cimg%20src=x%20onerror=alert(1)%3E')
    expect(document.querySelector('img')).toBeNull()
  })

  it.each([
    ['hi', 'पेज नहीं मिला', 'होम पेज पर जाएँ'],
    ['gu', 'પેજ મળ્યું નથી', 'હોમ પેજ પર જાઓ'],
  ])('is translated in %s', async (lng, title, home) => {
    await i18n.changeLanguage(lng)
    renderAt('/nope')
    expect(screen.getByRole('heading', { level: 1, name: title })).toBeTruthy()
    expect(screen.getByRole('link', { name: home })).toBeTruthy()
  })
})

describe('known routes are not swallowed by the catch-all', () => {
  it('"/" still renders the landing page for a logged-out visitor', () => {
    renderAt('/')
    expect(screen.queryByRole('heading', { name: 'Page not found' })).toBeNull()
  })

  it('a protected route still redirects a logged-out visitor home, not to 404', () => {
    renderAt('/app/history')
    expect(screen.queryByRole('heading', { name: 'Page not found' })).toBeNull()
  })
})
