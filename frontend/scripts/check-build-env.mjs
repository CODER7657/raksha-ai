// Fails the build when the env the bundle bakes in is missing or not a URL.
//
// Vite inlines `import.meta.env.VITE_*` as string literals at build time, so a
// bad value is not an error anywhere: it is a working bundle pointed at the
// wrong place. That is how the live site broke. The Vercel variable held the
// literal text `[SENSITIVE]`, the bundle shipped `fetch("[SENSITIVE]/api/...")`,
// the browser resolved that relative to the site itself, and every scan got the
// SPA's own index.html back with a 405. The build was green and the deploy was
// green.
//
// Wired into vite.config.ts, so `vite build`, `vercel build` and the dev server
// all refuse to start on a bad value. Tested by check-build-env.test.mjs.

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]'])

/** Returns an error message for `value`, or null when it is usable.
 *
 * The API base must be an origin only (`https://host[:port]`): every caller
 * appends a path that starts with `/`, so a trailing slash or a path here would
 * produce `//api/...` or a doubled prefix. Plain http is allowed only for a
 * local backend.
 */
export function apiBaseUrlError(value) {
  const name = 'VITE_API_BASE_URL'
  if (!value || !value.trim()) return `${name} is not set.`
  if (value !== value.trim()) return `${name} has leading or trailing whitespace.`

  let url
  try {
    url = new URL(value)
  } catch {
    return `${name} is not an absolute URL (got ${JSON.stringify(value)}).`
  }

  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    return `${name} must use https (got ${url.protocol}).`
  }
  if (url.protocol === 'http:' && !LOCAL_HOSTS.has(url.hostname)) {
    return `${name} may use plain http only for localhost (got ${url.host}).`
  }
  if (url.username || url.password) return `${name} must not contain credentials.`
  // Compared on the parts, not on `url.origin`, so an uppercase host or an
  // explicit default port is not mistaken for a path.
  if (url.pathname !== '/' || url.search || url.hash || value.endsWith('/')) {
    return `${name} must be an origin with no path, query or trailing slash (got ${JSON.stringify(value)}, expected ${JSON.stringify(url.origin)}).`
  }
  return null
}

/** The Supabase URL is baked in the same way and broke the same way would. */
export function supabaseUrlError(value) {
  const name = 'VITE_SUPABASE_URL'
  if (!value || !value.trim()) return `${name} is not set.`
  let url
  try {
    url = new URL(value)
  } catch {
    return `${name} is not an absolute URL (got ${JSON.stringify(value)}).`
  }
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && LOCAL_HOSTS.has(url.hostname))) {
    return `${name} must use https.`
  }
  return null
}

/** Never echoes the key: an anon key is public, but a pasted service-role key
 * would not be, and build logs are kept. */
export function supabaseAnonKeyError(value) {
  const name = 'VITE_SUPABASE_ANON_KEY'
  if (!value || !value.trim()) return `${name} is not set.`
  if (/^\[.*\]$/.test(value.trim())) return `${name} is a redaction placeholder, not a key.`
  return null
}

/** Every problem at once, so a broken dashboard is fixed in one pass. */
export function buildEnvErrors(env) {
  return [
    apiBaseUrlError(env.VITE_API_BASE_URL),
    supabaseUrlError(env.VITE_SUPABASE_URL),
    supabaseAnonKeyError(env.VITE_SUPABASE_ANON_KEY),
  ].filter(Boolean)
}

export function assertBuildEnv(env) {
  const errors = buildEnvErrors(env)
  if (errors.length) {
    throw new Error(
      'Refusing to build with a broken environment:\n  - ' +
        errors.join('\n  - ') +
        '\nLocally: copy .env.example to .env.local. On Vercel: Project → Settings → Environment Variables.',
    )
  }
}
