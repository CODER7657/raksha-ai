/** i18next setup.
 *
 * `i18next` and `react-i18next` were listed in package.json from the start but
 * never actually wired up — every string in the app was hardcoded English JSX.
 * That's why changing the language selector appeared to do nothing: it only
 * ever changed the `language` field sent to the API, never the interface.
 *
 * Translation coverage is intentionally partial. `en`, `hi` and `gu` are
 * complete; the other nine languages in `lib/languages.ts` have no bundle yet
 * and fall back to English via `fallbackLng`. That's a deliberate call — a
 * half-machine-translated fraud-safety UI is worse than an English one, since
 * a mistranslated safety instruction can cause real harm. Add the remaining
 * locales as native speakers review them.
 */

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import en from './locales/en.json'
import gu from './locales/gu.json'
import hi from './locales/hi.json'

/** Languages with a real, reviewed translation bundle. */
export const TRANSLATED_LANGUAGES = ['en', 'hi', 'gu'] as const

/** Keys that exist in `en` and deliberately not yet in `hi` or `gu`.
 *
 * Named rather than quietly absent, for the reason in the header above: a
 * machine translation of fraud-safety copy is worse than English, so the honest
 * state is "missing and tracked". This is the web counterpart of the
 * `knownUntranslated` map #71 added on the Android side, and it exists so the
 * gap is countable instead of being discovered by a Hindi user meeting English
 * text.
 *
 * `trace.noPatternsForLanguage` shipped with #88, which is the issue about
 * nine languages having no scam patterns at all — so a string explaining that
 * gap is itself waiting on the language review in #89. Remove entries here as
 * a speaker supplies them, in the same PR as the translation. */
export const KNOWN_UNTRANSLATED = ['trace.noPatternsForLanguage'] as const

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    hi: { translation: hi },
    gu: { translation: gu },
  },
  lng: 'en',
  fallbackLng: 'en',
  // React already escapes interpolated values; double-escaping mangles
  // apostrophes in the English copy.
  interpolation: { escapeValue: false },
  returnEmptyString: false,
})

export default i18n
