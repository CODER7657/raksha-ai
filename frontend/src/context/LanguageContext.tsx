/** One global language choice for the whole app.
 *
 * Before this, ChatPage, ScanInputPage and PracticePage each held their own
 * `useState('en')`. Picking Gujarati on the chat screen and then navigating to
 * Scan silently reset you to English, and nothing outside the API payload ever
 * reacted to the choice at all.
 *
 * This provider is the single source of truth: it persists the choice, drives
 * i18next for interface strings, and sets `lang`/`dir` on <html> so the browser
 * hyphenates, spell-checks and lays out right-to-left text correctly (Urdu).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import i18n, { TRANSLATED_LANGUAGES } from '../i18n'
import { LANGUAGES, type LanguageOption } from '../lib/languages'

export type LanguageCode = LanguageOption['code']

const STORAGE_KEY = 'raksha.language'
const DEFAULT_LANGUAGE: LanguageCode = 'en'

function isLanguageCode(value: string | null): value is LanguageCode {
  return !!value && LANGUAGES.some((l) => l.code === value)
}

/** Prefer a stored choice, then the browser's own language if we support it. */
function detectInitialLanguage(): LanguageCode {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (isLanguageCode(stored)) return stored
  } catch {
    // localStorage can throw in private mode / blocked-cookie contexts.
  }

  const browserBase = navigator.language?.split('-')[0]
  if (isLanguageCode(browserBase)) return browserBase

  return DEFAULT_LANGUAGE
}

interface LanguageContextValue {
  language: LanguageCode
  setLanguage: (code: LanguageCode) => void
  /** Full option record — label, BCP-47 speech tag, direction. */
  option: LanguageOption
  /** BCP-47 tag for speech synthesis, e.g. "gu-IN". */
  speechLang: string
  /** False when the UI falls back to English because this language has no
   * translation bundle yet — lets screens show an honest note instead of
   * pretending everything is translated. */
  isTranslated: boolean
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<LanguageCode>(detectInitialLanguage)

  const setLanguage = useCallback((code: LanguageCode) => {
    setLanguageState(code)
    try {
      window.localStorage.setItem(STORAGE_KEY, code)
    } catch {
      // Non-fatal: the choice just won't survive a reload.
    }
  }, [])

  const option = useMemo(
    () => LANGUAGES.find((l) => l.code === language) ?? LANGUAGES[0],
    [language],
  )

  useEffect(() => {
    // Untranslated languages resolve to the English bundle rather than showing
    // raw i18n keys on screen.
    const uiLanguage = (TRANSLATED_LANGUAGES as readonly string[]).includes(language) ? language : 'en'
    void i18n.changeLanguage(uiLanguage)

    document.documentElement.lang = language
    document.documentElement.dir = option.dir ?? 'ltr'
  }, [language, option])

  const value = useMemo<LanguageContextValue>(
    () => ({
      language,
      setLanguage,
      option,
      speechLang: option.speechLang,
      isTranslated: (TRANSLATED_LANGUAGES as readonly string[]).includes(language),
    }),
    [language, setLanguage, option],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside a LanguageProvider')
  return ctx
}
