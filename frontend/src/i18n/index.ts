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
