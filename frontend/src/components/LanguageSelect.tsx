/** The one language selector, used everywhere.
 *
 * Replaces three copy-pasted <select> blocks that each drove their own local
 * useState, so the choice now follows the user across every screen.
 */

import { useTranslation } from 'react-i18next'
import { useLanguage, type LanguageCode } from '../context/LanguageContext'
import { LANGUAGES } from '../lib/languages'

interface LanguageSelectProps {
  /** Extra classes for the <select>, so pages keep their own spacing. */
  className?: string
}

export function LanguageSelect({ className = '' }: LanguageSelectProps) {
  const { language, setLanguage } = useLanguage()
  const { t } = useTranslation()

  return (
    <select
      value={language}
      onChange={(e) => setLanguage(e.target.value as LanguageCode)}
      aria-label={t('common.selectLanguage')}
      className={`border border-ink bg-white px-2 py-1 text-[11px] text-ink focus:outline-none focus:ring-2 focus:ring-accent ${className}`}
    >
      {LANGUAGES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.label}
        </option>
      ))}
    </select>
  )
}
