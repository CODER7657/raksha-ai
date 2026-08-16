package ai.raksha.app.core

import android.content.Context

/**
 * The two settings the SMS path needs: whether scanning is on, and which
 * language to score and explain in.
 *
 * Plain `SharedPreferences` is fine for exactly this content — a boolean and a
 * language code, neither sensitive. Keystore-backed encrypted storage is for
 * the **session token**, which is a different thing and does not live here.
 * Nothing message-derived is stored: no scanned text, no verdicts, no history.
 * Adding any of that would need encryption and one-tap clearing.
 *
 * **Deliberately credential-encrypted, not device-encrypted.** #91 §2 proposed
 * moving this to device-encrypted storage so `SmsReceiver` could read it while
 * the phone is locked after a reboot. That was tried and reverted: the platform
 * does not deliver `SMS_RECEIVED` to us during that window at all, with or
 * without `android:directBootAware`, so the receiver never runs and has nothing
 * to read. Device-encrypted storage is readable earlier in boot and therefore a
 * weaker guarantee, and buying nothing with it is a bad trade. The measurements
 * are in `AndroidManifest.xml` next to the receiver.
 */
class ScanPreferences(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("raksha_scan", Context.MODE_PRIVATE)

    /**
     * Off until the user turns it on. Holding RECEIVE_SMS is not consent to act
     * on it, and a security product that starts reading messages the moment it
     * is installed earns the suspicion it would deserve.
     *
     * Switching it **on** also stamps [acknowledgedInterruptionMillis], which
     * scopes the force-stop notice to interruptions after protection was
     * actually claimed. Without it the default of `0L` meant any force-stop in
     * the app's whole history counted — including ones from before the user had
     * ever enabled scanning, when nothing had been promised and so nothing was
     * missed. Same false-alarm class that crashes and low-memory kills are
     * deliberately excluded from in [InterruptionMonitor], arriving from the
     * other end (#98 §6).
     *
     * Done in the setter rather than at the call sites so that a future way of
     * enabling scanning cannot forget it. Only on the `true` edge: turning
     * scanning off must not silently dismiss a notice the user has not read.
     */
    var isScanningEnabled: Boolean
        get() = prefs.getBoolean(KEY_ENABLED, false)
        set(value) {
            val wasEnabled = prefs.getBoolean(KEY_ENABLED, false)
            val edit = prefs.edit().putBoolean(KEY_ENABLED, value)
            if (value && !wasEnabled) {
                edit.putLong(KEY_ACKNOWLEDGED_INTERRUPTION, System.currentTimeMillis())
            }
            edit.apply()
        }

    /** Language code understood by the rule engine; defaults to English. */
    var language: String
        get() = prefs.getString(KEY_LANGUAGE, DEFAULT_LANGUAGE) ?: DEFAULT_LANGUAGE
        set(value) = prefs.edit().putString(KEY_LANGUAGE, value).apply()

    /**
     * When the user last acknowledged being told the app had been force-stopped,
     * so the notice appears once per interruption rather than on every launch.
     *
     * A timestamp, not message-derived: it records something Android did to this
     * app, not anything about what arrived.
     */
    var acknowledgedInterruptionMillis: Long
        get() = prefs.getLong(KEY_ACKNOWLEDGED_INTERRUPTION, 0L)
        set(value) = prefs.edit().putLong(KEY_ACKNOWLEDGED_INTERRUPTION, value).apply()

    private companion object {
        const val KEY_ENABLED = "scanning_enabled"
        const val KEY_LANGUAGE = "language"
        const val KEY_ACKNOWLEDGED_INTERRUPTION = "acknowledged_interruption_millis"
        const val DEFAULT_LANGUAGE = "en"
    }
}
