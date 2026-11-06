// Run with `npm test` (node's built-in runner, no extra dependency).

import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  apiBaseUrlError,
  assertBuildEnv,
  buildEnvErrors,
  supabaseAnonKeyError,
  supabaseUrlError,
} from './check-build-env.mjs'

const GOOD = {
  VITE_API_BASE_URL: 'https://raksha-ai-c5yu.onrender.com',
  VITE_SUPABASE_URL: 'https://abcdefghijklmnop.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiJ9.e30.sig',
}

test('accepts the production backend origin', () => {
  assert.equal(apiBaseUrlError('https://raksha-ai-c5yu.onrender.com'), null)
})

test('accepts plain http for a local backend only', () => {
  assert.equal(apiBaseUrlError('http://localhost:8000'), null)
  assert.equal(apiBaseUrlError('http://127.0.0.1:8000'), null)
  assert.equal(apiBaseUrlError('http://[::1]:8000'), null)
  assert.match(apiBaseUrlError('http://raksha-ai-c5yu.onrender.com'), /only for localhost/)
})

test('rejects the redaction placeholder that broke the live site', () => {
  assert.match(apiBaseUrlError('[SENSITIVE]'), /not an absolute URL/)
})

test('rejects missing, empty and whitespace values', () => {
  for (const value of [undefined, '', '   ']) {
    assert.match(apiBaseUrlError(value), /not set/)
  }
  assert.match(apiBaseUrlError(' https://a.example '), /whitespace/)
})

test('rejects relative and host-only values', () => {
  for (const value of ['/api', 'raksha-ai-c5yu.onrender.com', '//raksha.example']) {
    assert.match(apiBaseUrlError(value), /not an absolute URL/)
  }
})

test('rejects non-web schemes', () => {
  assert.match(apiBaseUrlError('ftp://a.example'), /must use https/)
  assert.match(apiBaseUrlError('javascript:alert(1)'), /must use https/)
})

test('rejects a trailing slash, path, query or fragment', () => {
  for (const value of [
    'https://a.example/',
    'https://a.example/api',
    'https://a.example?x=1',
    'https://a.example#x',
  ]) {
    assert.match(apiBaseUrlError(value), /must be an origin/)
  }
})

test('accepts an uppercase host or an explicit default port', () => {
  assert.equal(apiBaseUrlError('https://Raksha.Example'), null)
  assert.equal(apiBaseUrlError('https://raksha.example:443'), null)
  assert.equal(apiBaseUrlError('http://localhost:8000'), null)
})

test('rejects embedded credentials', () => {
  assert.match(apiBaseUrlError('https://u:p@a.example'), /credentials/)
})

test('supabase URL must be an https URL', () => {
  assert.equal(supabaseUrlError(GOOD.VITE_SUPABASE_URL), null)
  assert.equal(supabaseUrlError('http://localhost:54321'), null)
  assert.match(supabaseUrlError(''), /not set/)
  assert.match(supabaseUrlError('[SENSITIVE]'), /not an absolute URL/)
  assert.match(supabaseUrlError('http://x.supabase.co'), /https/)
})

test('anon key must be present and not a placeholder, and is never echoed', () => {
  assert.equal(supabaseAnonKeyError(GOOD.VITE_SUPABASE_ANON_KEY), null)
  assert.match(supabaseAnonKeyError(undefined), /not set/)
  assert.match(supabaseAnonKeyError('[SENSITIVE]'), /placeholder/)
  assert.doesNotMatch(supabaseAnonKeyError('[secret-value]'), /secret-value/)
})

test('a good env builds', () => {
  assert.deepEqual(buildEnvErrors(GOOD), [])
  assert.doesNotThrow(() => assertBuildEnv(GOOD))
})

test('every problem is reported at once', () => {
  const errors = buildEnvErrors({})
  assert.equal(errors.length, 3)
  assert.throws(() => assertBuildEnv({ ...GOOD, VITE_API_BASE_URL: '[SENSITIVE]' }), /VITE_API_BASE_URL/)
})
