// Fails the build when the web's tokens drift from design/tokens.json.
//
// The Android theme is GENERATED from that file, so it cannot drift. The web
// cannot be generated the same way without owning Tailwind's `@theme` block, so
// it is asserted instead — #116 §2 asks for "generated or asserted, never
// hand-copied", and this is the asserted half.
//
// This is the same shape of gap as #99: #64 gave Android an i18n drift guard,
// the web had none, and a key added afterwards went straight through. Two
// platforms, one concern, and only one of them checked. Rather than repeat that
// for colour, both halves land together.
//
// Runs as `prebuild`, alongside check-i18n-parity.mjs, so `npm run build`
// enforces it in CI and locally without a workflow change.

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const tokensPath = join(here, '..', '..', 'design', 'tokens.json')
const cssPath = join(here, '..', 'src', 'index.css')
const verdictPath = join(here, '..', 'src', 'lib', 'scanResult.ts')

const tokens = JSON.parse(readFileSync(tokensPath, 'utf8'))
const css = readFileSync(cssPath, 'utf8')
const verdictSource = readFileSync(verdictPath, 'utf8')

const problems = []

/** Every `--name: value;` inside the @theme block. */
const themeBlock = css.match(/@theme\s*\{([\s\S]*?)\n\}/)
if (!themeBlock) {
  problems.push(
    'No @theme block found in src/index.css. The brand tokens live there and ' +
      'are checked against design/tokens.json.',
  )
}

const declared = new Map()
if (themeBlock) {
  for (const line of themeBlock[1].split('\n')) {
    const m = line.match(/^\s*(--[\w-]+)\s*:\s*(.+?);\s*$/)
    if (m) declared.set(m[1], m[2].trim())
  }
}

const named = (group) =>
  Object.entries(tokens[group] ?? {}).filter(([key]) => !key.startsWith('$'))

// --- Brand colours and fonts must appear verbatim in @theme -----------------

for (const group of ['color', 'font']) {
  for (const [name, token] of named(group)) {
    const cssVar = token.css
    if (!cssVar) continue
    const expected = token.value
    const actual = declared.get(cssVar)

    if (actual === undefined) {
      problems.push(
        `${cssVar} is missing from @theme in src/index.css. ` +
          `design/tokens.json defines ${group}.${name} = ${expected}.`,
      )
    } else if (actual.toLowerCase() !== expected.toLowerCase()) {
      problems.push(
        `${cssVar} is ${actual} in src/index.css but ${expected} in ` +
          `design/tokens.json. Change the token file — it is the source of ` +
          `truth, and the Android theme is generated from it.`,
      )
    }
  }
}

// --- Verdict semantics ------------------------------------------------------
//
// The verdict colours are also exposed as @theme vars so Tailwind generates
// `bg-verdict-*` utilities, and VERDICT_META must use them rather than a raw
// palette class. A verdict rendered emerald on the site and #009966 on the
// phone would be the same colour today and diverge the moment either side is
// retinted — which is exactly the drift this file exists to stop.

for (const [name, token] of named('verdict')) {
  const cssVar = token.css
  const expected = token.value
  const actual = declared.get(cssVar)

  if (actual === undefined) {
    problems.push(
      `${cssVar} is missing from @theme in src/index.css. Without it Tailwind ` +
        `cannot generate the bg-verdict-* utility that VERDICT_META needs.`,
    )
  } else if (actual.toLowerCase() !== expected.toLowerCase()) {
    problems.push(`${cssVar} is ${actual} in src/index.css but ${expected} in design/tokens.json.`)
  }

  // `high_risk` -> `high-risk`, matching the CSS var suffix.
  const utility = `bg-${cssVar.replace('--color-', '')}`

  // Scoped to this verdict's own entry, not the whole file. Checking
  // `source.includes(utility)` was the first version and it was too weak:
  // reverting `badgeClass` to `bg-red-600` still passed, because `barClass`
  // on the same line kept the token utility present somewhere in the file.
  // A guard that cannot fail is worse than none, so it is pinned per entry.
  const entry = verdictSource.match(new RegExp(`^\\s*${name}:\\s*\\{.*$`, 'm'))
  if (!entry) {
    problems.push(
      `VERDICT_META in src/lib/scanResult.ts has no \`${name}:\` entry. Every ` +
        `verdict in design/tokens.json needs one.`,
    )
    continue
  }

  const line = entry[0]
  const classAttributes = [...line.matchAll(/\b(badgeClass|barClass):\s*'([^']*)'/g)]
  if (classAttributes.length === 0) {
    problems.push(`VERDICT_META.${name} declares no badgeClass or barClass.`)
  }
  for (const [, attribute, value] of classAttributes) {
    if (!value.split(/\s+/).includes(utility)) {
      problems.push(
        `VERDICT_META.${name}.${attribute} is '${value}', which does not use ` +
          `\`${utility}\`. Verdict colours must come from the shared tokens so ` +
          `the web and Android paint the same verdict the same way (#116 §2). ` +
          `If it still uses ${token.was ?? 'a raw palette class'}, that is the drift.`,
      )
    }
  }

  if (token.labelKey && !verdictSource.includes(token.labelKey)) {
    problems.push(
      `VERDICT_META does not reference the label key \`${token.labelKey}\` for ${name}.`,
    )
  }
}

if (problems.length > 0) {
  console.error('\nDesign tokens have drifted from design/tokens.json:\n')
  for (const problem of problems) console.error(`  - ${problem}`)
  console.error(
    '\ndesign/tokens.json is the source of truth. The Android Compose theme is\n' +
      'generated from it; this script asserts the web matches. Fix the token file\n' +
      'first, then both sides.\n',
  )
  process.exit(1)
}

console.log(
  `Design tokens match: ${named('color').length} brand, ${named('verdict').length} verdict, ` +
    `${named('font').length} font.`,
)
