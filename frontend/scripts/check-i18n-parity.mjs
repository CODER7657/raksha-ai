// Fails the build when a shipped locale is missing a key English has.
//
// #64 gave the Android side this check and the web side never had one. The gap
// it exists to catch landed almost immediately: #88 added
// `trace.noPatternsForLanguage` to en.json only, so a Hindi user reading a
// Hindi verdict got an English sentence explaining why that verdict was
// ungrounded.
//
// That failure is invisible by construction. i18next's `fallbackLng: 'en'`
// means a missing key still renders *something*, in a language the reader may
// not have, and nothing logs. The only way it surfaces is somebody noticing.
//
// Runs as `prebuild`, so `npm run build` enforces it in CI and locally without
// needing a workflow change.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const localesDir = join(here, '..', 'src', 'i18n', 'locales')

// Locales with a complete bundle. Must match TRANSLATED_LANGUAGES in
// src/i18n/index.ts — the other nine deliberately have no bundle and fall back
// to English, which is a stated choice rather than a gap.
const SHIPPED = ['hi', 'gu']

// Keys allowed to be absent, with the reason. Not a convenience hatch: a
// machine translation of a scam warning is the harm `i18n/index.ts` warns
// about, so "missing and named" beats "filled in by whoever was here".
const KNOWN_GAPS = {
  'android.rule_generic_warning': 'No translation yet — tracked in #52 (native-speaker review).',
}

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) =>
    v !== null && typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v]],
  )

const load = (locale) =>
  new Map(flatten(JSON.parse(readFileSync(join(localesDir, `${locale}.json`), 'utf8'))))

const english = load('en')
const problems = []

for (const locale of SHIPPED) {
  const bundle = load(locale)

  for (const key of english.keys()) {
    if (!bundle.has(key) && !(key in KNOWN_GAPS)) {
      problems.push(`  ${locale}: missing ${key}`)
    }
  }
  // An extra key is dead weight and, worse, suggests coverage that is not
  // there — nothing renders it, so it reads as translated when it is not.
  for (const key of bundle.keys()) {
    if (!english.has(key)) problems.push(`  ${locale}: has ${key}, which en does not`)
  }
}

if (problems.length > 0) {
  console.error(
    `\ni18n parity check failed:\n\n${problems.join('\n')}\n\n` +
      `A key present in en and missing from a shipped locale falls back to English\n` +
      `silently — the reader gets a language they may not have, and nothing logs it.\n\n` +
      `Add the translation, or list it in KNOWN_GAPS in this script with the issue\n` +
      `tracking it. Do not paste in a machine translation of the English: a\n` +
      `mistranslated safety instruction is worse than an English one.\n`,
  )
  process.exit(1)
}

const known = Object.keys(KNOWN_GAPS).length
console.log(
  `i18n parity: ${english.size} keys x ${SHIPPED.length} locales` +
    (known > 0 ? ` (${known} known gap${known > 1 ? 's' : ''}, see #52)` : ''),
)
