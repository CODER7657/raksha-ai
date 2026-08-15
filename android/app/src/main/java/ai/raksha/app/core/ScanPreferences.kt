package ai.raksha.app.core

import android.content.Context

/**
 * The two settings the SMS path needs: whether scanning is on, and which
 * language to score and explain in.
 *
 * Plain `SharedPreferences` is fine for exactly this content — a boolean and a
 * language code, neither sensitive. #29 §3 requires Keystore-backed encrypted
 * storage for the **session token**, which is a different thing and does not
 * live here. Nothing message-derived is stored: no scanned text, no verdicts,
 * no history. Adding any of that would need the encryption and one-tap clearing
 * described in #29 §2.
 */
class ScanPreferences(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("raksha_scan", Context.MODE_PRIVATE)

    /**
     * Off until the user turns it on. Holding RECEIVE_SMS is not consent to act
     * on it, and a security product that starts reading messages the moment it
     * is installed earns the suspicion it would deserve.
     */
    var isScanningEnabled: Boolean
        get() = prefs.getBoolean(KEY_ENABLED, false)
        set(value) = prefs.edit().putBoolean(KEY_ENABLED, value).apply()

    /** Language code understood by the rule engine; defaults to English. */
    var language: String
        get() = prefs.getString(KEY_LANGUAGE, DEFAULT_LANGUAGE) ?: DEFAULT_LANGUAGE
        set(value) = prefs.edit().putString(KEY_LANGUAGE, value).apply()

    private companion object {
        const val KEY_ENABLED = "scanning_enabled"
        const val KEY_LANGUAGE = "language"
        const val DEFAULT_LANGUAGE = "en"
    }
}
