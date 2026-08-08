export interface LanguageOption {
  code: 'en' | 'hi' | 'gu' | 'mr' | 'bn' | 'ta' | 'te' | 'kn' | 'ml' | 'pa' | 'or' | 'ur'
  label: string
  /** BCP-47 tag used to pick a speechSynthesis voice for read-aloud. */
  speechLang: string
  /** Writing direction — only Urdu is right-to-left here. Applied to <html>
   * by LanguageProvider so layout and text selection behave correctly. */
  dir?: 'ltr' | 'rtl'
}

/** Keep in sync with `LANGUAGES` in backend/app/core/languages.py and the
 * `LanguageCode` literals in backend/app/routes/{chat,scan}.py. */
export const LANGUAGES: LanguageOption[] = [
  { code: 'en', label: 'English', speechLang: 'en-IN' },
  { code: 'hi', label: 'हिन्दी (Hindi)', speechLang: 'hi-IN' },
  { code: 'gu', label: 'ગુજરાતી (Gujarati)', speechLang: 'gu-IN' },
  { code: 'mr', label: 'मराठी (Marathi)', speechLang: 'mr-IN' },
  { code: 'bn', label: 'বাংলা (Bengali)', speechLang: 'bn-IN' },
  { code: 'ta', label: 'தமிழ் (Tamil)', speechLang: 'ta-IN' },
  { code: 'te', label: 'తెలుగు (Telugu)', speechLang: 'te-IN' },
  { code: 'kn', label: 'ಕನ್ನಡ (Kannada)', speechLang: 'kn-IN' },
  { code: 'ml', label: 'മലയാളം (Malayalam)', speechLang: 'ml-IN' },
  { code: 'pa', label: 'ਪੰਜਾਬੀ (Punjabi)', speechLang: 'pa-IN' },
  { code: 'or', label: 'ଓଡ଼ିଆ (Odia)', speechLang: 'or-IN' },
  { code: 'ur', label: 'اردو (Urdu)', speechLang: 'ur-IN', dir: 'rtl' },
]
