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
// Every entry here is a gap being *named*, never one being accepted. A machine
// translation of a safety instruction reads as authoritative while being wrong
// about the sentence that has to be right, which is why the message below
// refuses one and why these sit in a list instead.
const KNOWN_GAPS = {
  'android.rule_generic_warning': 'No translation yet — tracked in #52 (native-speaker review).',

  // Layer 3, #116 §4. A Hindi or Gujarati speaker sees the call-screening
  // feature entirely in English, which for the senior citizen
  // THREAT-LANDSCAPE §02 designs for is close to not having it. @Ayush3422
  // owns language and supplies these before the feature is called shipped in
  // any locale but English. Tracked in #52 with the rest.
  //
  // The Android build has its own list of the same eight keys, in
  // app/build.gradle.kts. Two mechanisms for one concern is exactly what
  // #116 §2 is about, and this comment is the seam until they are one.
  'android.call_warning_title': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_heading': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_on': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_off': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_enable': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_explainer': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_unsupported': 'No translation yet — #116 §4, tracked in #52.',
  'android.call_screening_nothing_known': 'No translation yet — #116 §4, tracked in #52.',
}

const flatten = (obj, prefix = '') =>
  Object.entries(obj).flatMap(([k, v]) =>
    v !== null && typeof v === 'object' ? flatten(v, `${prefix}${k}.`) : [[`${prefix}${k}`, v]],
  )

const load = (locale) =>
  new Map(flatten(JSON.parse(readFileSync(join(localesDir, `${locale}.json`), 'utf8'))))

const english = load('en')
const bundles = new Map(SHIPPED.map((locale) => [locale, load(locale)]))
const problems = []
const staleGaps = []

for (const [locale, bundle] of bundles) {
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

// Every named gap must still BE a gap.
//
// Without this the list is a permission rather than a statement, and it decays
// in the one direction that matters. An entry whose translation has since
// landed is never revisited, so if that translation is later deleted the key is
// still allowed to be missing — a closed gap reopening in exactly the silence
// the list exists to prevent. The printed "(N known gaps)" quietly overcounts
// too, which is how a list nobody rereads stays plausible.
//
// Same shape as the schema test that makes every optional field explain itself:
// the allowlist has to justify each of its own entries on every run.
for (const key of Object.keys(KNOWN_GAPS)) {
  if (!english.has(key)) {
    staleGaps.push(`  ${key} — en does not have this key at all`)
    continue
  }
  const missingSomewhere = [...bundles.values()].some((bundle) => !bundle.has(key))
  if (!missingSomewhere) {
    staleGaps.push(`  ${key} — every shipped locale has it now`)
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

if (staleGaps.length > 0) {
  console.error(
    `\ni18n parity check failed — KNOWN_GAPS is out of date:\n\n${staleGaps.join('\n')}\n\n` +
      `A gap that is no longer a gap is not harmless. It makes the count above a\n` +
      `lie, and it leaves the key permitted to go missing again — so a translation\n` +
      `someone did could be deleted later and nothing would say so.\n\n` +
      `Delete the entry from KNOWN_GAPS. If the Android build lists the same key\n` +
      `in knownUntranslated (app/build.gradle.kts), delete it there too.\n`,
  )
  process.exit(1)
}

const known = Object.keys(KNOWN_GAPS).length
console.log(
  `i18n parity: ${english.size} keys x ${SHIPPED.length} locales` +
    (known > 0 ? ` (${known} known gap${known > 1 ? 's' : ''}, see #52)` : ''),
)
