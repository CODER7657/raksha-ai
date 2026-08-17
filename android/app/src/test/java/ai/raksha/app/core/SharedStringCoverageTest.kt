package ai.raksha.app.core

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * The shared UI strings the app renders come from the web app's bundles (#64).
 *
 * Cross-locale coverage — a key present in `en` and missing from `hi` — is
 * enforced by the generator in `app/build.gradle.kts`, which fails the build.
 * Repeating it here would only duplicate a check that already cannot be
 * skipped.
 *
 * What the generator *cannot* see is this file's subject: a hand-written string
 * in `values/strings.xml` with the same name as a generated one. Android
 * resource merging picks one, the other is silently discarded, and both
 * platforms look correct in review while the phone keeps stale wording. That is
 * the worst version of the drift #64 exists to stop, because nothing else in
 * the pipeline would notice.
 */
class SharedStringCoverageTest {

    /**
     * The complete set of strings that stay hand-written, with the reasoning in
     * the header of `values/strings.xml`.
     *
     * Asserting the exact set — rather than "no overlap" — is what makes the
     * shadowing impossible: if `values/strings.xml` holds only these, it cannot
     * contain a name the generator also emits. It also forces a decision when
     * someone adds a string, instead of letting the hand-written file quietly
     * grow back.
     */
    private val androidOnly = setOf(
        "app_name",
        "warning_channel_name",
        "warning_channel_description",
        "warning_summary",
        "warning_summary_no_sender",
        "warning_reason_bullet",
        "selected_format",
        // %1$d, same reason as selected_format: i18next writes {{count}} and
        // converting between the two invites a silent mismatch in the one place
        // a wrong format string crashes at render rather than at build (#116 §3).
        "settings_stored_count",
        // Layer 3's notification channel (#116 §4). Same reason as
        // warning_channel_*: a channel is an Android concept rendered by system
        // settings, and the web has no surface that shows either of these.
        // A separate channel from the message warnings because they interrupt
        // differently, and a channel is the only granularity Android gives a
        // user to want one and not the other.
        "call_channel_name",
        "call_channel_description",
        // %1$s, the same formatting-primitive reason as warning_summary. The
        // sentence a user reads about the caller is call_warning_title, which
        // lives in the web bundle where it belongs.
        "call_warning_summary",
    )

    private fun declaredIn(path: String): Set<String> =
        Regex("""<string name="([^"]+)"""")
            .findAll(File(path).readText())
            .map { it.groupValues[1] }
            .toSet()

    @Test
    fun `values holds exactly the strings we decided to keep hand-written`() {
        assertEquals(
            androidOnly,
            declaredIn("src/main/res/values/strings.xml"),
            "values/strings.xml has drifted from the agreed Android-only set. Anything " +
                "user-facing that also exists on the web belongs in " +
                "frontend/src/i18n/locales/*.json under android.* (#64), where the two " +
                "platforms cannot describe the same thing differently. If this string " +
                "genuinely has no web counterpart, add it to androidOnly with the reason.",
        )
    }

    @Test
    fun `translated locales carry no string the default locale lacks`() {
        // An orphan in values-hi is a string that can never be shown: resource
        // lookup falls back to the default, so a Hindi-only name resolves to
        // nothing on any other device and to itself on none.
        listOf("values-hi", "values-gu").forEach { folder ->
            val orphans = declaredIn("src/main/res/$folder/strings.xml") - androidOnly
            assertEquals(
                emptySet(),
                orphans,
                "$folder declares $orphans, which the default locale does not. Either it " +
                    "moved to the web bundle and this copy was left behind, or it needs " +
                    "adding to values/strings.xml.",
            )
        }
    }

    @Test
    fun `the web bundles are reachable from the android build`() {
        // The generator reads outside the Gradle root. If someone copies
        // `android/` out of the monorepo this is the first thing that breaks,
        // and the failure deep inside JsonSlurper says nothing useful.
        val locales = File("../../frontend/src/i18n/locales")
        assertTrue(
            locales.isDirectory,
            "cannot reach the web i18n bundles at ${locales.canonicalPath}. The Android " +
                "build reads its user-facing strings from them (#64), so `android/` only " +
                "builds inside a full checkout of the repository.",
        )
        listOf("en", "hi", "gu").forEach {
            assertTrue(File(locales, "$it.json").isFile, "missing bundle: $it.json")
        }
    }
}
