package ai.raksha.app.core

/**
 * The languages Raksha AI supports, mirrored from the backend.
 *
 * This is a third copy of a list that already exists twice. The backend's
 * `app/core/languages.py` is the source of truth and names its own consumers;
 * this file is now one of them. When a language is added or a code changes,
 * all of these move together:
 *
 *   - `backend/app/core/languages.py`            (source of truth)
 *   - `LanguageCode` in `backend/app/routes/scan.py` and `chat.py`
 *   - `frontend/src/lib/languages.ts`
 *   - this file
 *
 * Why duplicate rather than fetch: the SMS listener scores messages with no
 * network at all, so the language a message is scored in has to be known
 * offline. A list fetched at runtime would make the offline path depend on
 * having once been online.
 */
enum class Language(
    val code: String,
    val englishName: String,
    val nativeName: String,
    val script: String,
    /** BCP-47 tag, used for on-device TTS voice matching. */
    val bcp47: String,
) {
    EN("en", "English", "English", "Latin", "en-IN"),
    HI("hi", "Hindi", "हिन्दी", "Devanagari", "hi-IN"),
    GU("gu", "Gujarati", "ગુજરાતી", "Gujarati", "gu-IN"),
    MR("mr", "Marathi", "मराठी", "Devanagari", "mr-IN"),
    BN("bn", "Bengali", "বাংলা", "Bengali", "bn-IN"),
    TA("ta", "Tamil", "தமிழ்", "Tamil", "ta-IN"),
    TE("te", "Telugu", "తెలుగు", "Telugu", "te-IN"),
    KN("kn", "Kannada", "ಕನ್ನಡ", "Kannada", "kn-IN"),
    ML("ml", "Malayalam", "മലയാളം", "Malayalam", "ml-IN"),
    PA("pa", "Punjabi", "ਪੰਜਾਬੀ", "Gurmukhi", "pa-IN"),
    OR("or", "Odia", "ଓଡ଼ିଆ", "Odia", "or-IN"),
    UR("ur", "Urdu", "اردو", "Arabic (Nastaliq)", "ur-IN");

    companion object {
        val DEFAULT = EN

        private val byCode = entries.associateBy(Language::code)

        /**
         * Never throws — an unknown code falls back to English, matching
         * `get_language()` on the backend. A bad stored preference should not
         * crash the SMS receiver.
         */
        fun fromCode(code: String?): Language = byCode[code?.lowercase()] ?: DEFAULT
    }
}
