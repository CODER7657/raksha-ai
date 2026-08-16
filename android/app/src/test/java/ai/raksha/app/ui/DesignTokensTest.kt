package ai.raksha.app.ui

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * The Android half of the design-token contract (#116 §2).
 *
 * `design/tokens.json` is the source of truth. `DesignTokens.kt` is generated
 * from it at build time and the web side is asserted against it by
 * `frontend/scripts/check-design-tokens.mjs`. This closes the remaining hole:
 * a generated file is only as good as the generation having actually run, and a
 * stale `DesignTokens.kt` from an earlier token set would compile perfectly.
 *
 * Reads the JSON directly rather than trusting the build, so this fails if the
 * generator silently produced the wrong thing — not only if it did not run.
 */
class DesignTokensTest {

    private fun tokensFile(): File {
        var dir: File? = File(System.getProperty("user.dir"))
        while (dir != null) {
            val candidate = File(dir, "design/tokens.json")
            if (candidate.isFile) return candidate
            dir = dir.parentFile
        }
        fail("Could not find design/tokens.json from ${System.getProperty("user.dir")}")
    }

    /**
     * Minimal extraction of `"name": { "value": "#rrggbb" }` within a top-level
     * group. Deliberately not a JSON parser: the production source set of this
     * module has no dependencies, and adding one so a test can read six colours
     * would be a poor trade.
     */
    private fun colours(group: String): Map<String, String> {
        val json = tokensFile().readText()
        val groupStart = json.indexOf("\"$group\"")
        if (groupStart < 0) fail("design/tokens.json has no `$group` group")

        // The group's object runs to the next top-level key at the same depth;
        // scanning braces is enough for a file this shape.
        var depth = 0
        var index = json.indexOf('{', groupStart)
        val start = index
        while (index < json.length) {
            when (json[index]) {
                '{' -> depth++
                '}' -> {
                    depth--
                    if (depth == 0) break
                }
            }
            index++
        }
        val body = json.substring(start, index + 1)

        return Regex("\"([A-Za-z_]+)\"\\s*:\\s*\\{[^}]*?\"value\"\\s*:\\s*\"(#[0-9a-fA-F]{6})\"")
            .findAll(body)
            .associate { it.groupValues[1] to it.groupValues[2].lowercase() }
    }

    /** Compose packs colours as ARGB; the tokens are `#rrggbb` at full alpha. */
    private fun hexOf(colour: androidx.compose.ui.graphics.Color): String {
        val argb = colour.value shr 32
        return "#%06x".format(argb.toLong() and 0xFFFFFF)
    }

    @Test
    fun `brand colours match the token file`() {
        val expected = colours("color")
        assertTrue(expected.isNotEmpty(), "no brand colours parsed — the test is vacuous")

        val actual = mapOf(
            "ink" to DesignTokens.ink,
            "paper" to DesignTokens.paper,
            "line" to DesignTokens.line,
            "accent" to DesignTokens.accent,
            "accentInk" to DesignTokens.accentInk,
        )

        assertEquals(
            expected.keys,
            actual.keys,
            "design/tokens.json and DesignTokens.kt disagree about which brand " +
                "colours exist. If a token was added, this test needs the new name too.",
        )
        expected.forEach { (name, hex) ->
            assertEquals(hex, hexOf(actual.getValue(name)), "brand colour `$name`")
        }
    }

    @Test
    fun `verdict colours match the token file`() {
        val expected = colours("verdict")
        assertTrue(expected.isNotEmpty(), "no verdict colours parsed — the test is vacuous")

        expected.forEach { (name, hex) ->
            val colour = DesignTokens.Verdict.byName[name]
                ?: fail("DesignTokens.Verdict.byName has no `$name`, but tokens.json does")
            assertEquals(hex, hexOf(colour), "verdict colour `$name`")
        }
    }

    @Test
    fun `verdict names match the backend's verdict strings`() {
        // These are the three values `_validate_result_shape` accepts in
        // backend/app/services/llm.py. A verdict the phone cannot colour would
        // fall through to whatever default the call site picked.
        assertEquals(
            setOf("safe", "suspicious", "high_risk"),
            DesignTokens.Verdict.byName.keys,
            "verdict token names must match the backend's verdict vocabulary",
        )
    }

    @Test
    fun `the theme uses the accent rather than a Material default`() {
        // The regression this whole change exists to prevent: the app ran on a
        // bare MaterialTheme, so every button was Material's default purple
        // while the website had a brand.
        assertEquals(hexOf(DesignTokens.accent), hexOf(RakshaColorScheme.primary))
        assertEquals(hexOf(DesignTokens.paper), hexOf(RakshaColorScheme.background))
        assertEquals(hexOf(DesignTokens.ink), hexOf(RakshaColorScheme.onBackground))
    }

    /**
     * Every colour role on [androidx.compose.material3.ColorScheme], found by
     * reflection rather than listed.
     *
     * `Color` is a value class, so its property getters compile to
     * name-mangled methods returning a raw `long` — `getPrimary-0d7_KjU()`.
     * That is what is walked here; the suffix is stripped to recover the role
     * name.
     *
     * Reflective on purpose. The first version of this test listed 24 roles by
     * hand and asserted each was a brand colour, which reads as completeness
     * and is not: a hand-written list of the thing you are checking for
     * completeness cannot establish completeness. `ColorScheme` has more roles
     * than that, and the ones left unset keep Material's own tonal defaults —
     * `surfaceContainer*` among them, which is where `Card` and menu surfaces
     * actually take their background from. A Card could have rendered lavender
     * with the test green.
     *
     * Done this way, a role added by a Compose upgrade fails loudly instead of
     * arriving purple.
     */
    private fun schemeRoles(): Map<String, String> {
        val scheme = RakshaColorScheme
        val roles = scheme.javaClass.methods
            .filter {
                it.parameterCount == 0 &&
                    it.returnType == java.lang.Long.TYPE &&
                    it.name.startsWith("get")
            }
            .associate { method ->
                val raw = method.invoke(scheme) as Long
                val name = method.name.removePrefix("get")
                    .substringBefore('-')
                    .replaceFirstChar(Char::lowercase)
                // Same packing as Color.value: ARGB in the high 32 bits.
                name to "#%06x".format((raw ushr 32) and 0xFFFFFF)
            }
        assertTrue(
            roles.size >= 24,
            "reflection found only ${roles.size} colour roles on ColorScheme, which " +
                "is fewer than the scheme sets by hand — the walk is broken and this " +
                "test would pass vacuously.",
        )
        return roles
    }

    @Test
    fun `every colour role on the scheme comes from a token`() {
        val brand = (colours("color") + colours("verdict")).values.toSet()

        val offBrand = schemeRoles().filterValues { it !in brand }
        assertTrue(
            offBrand.isEmpty(),
            "these colour roles are not brand tokens, so Material's tonal default " +
                "renders instead — a Card or menu surface can still come out " +
                "lavender:\n" +
                offBrand.entries.sortedBy { it.key }.joinToString("\n") {
                    "    ${it.key} = ${it.value}"
                } +
                "\n  Map each to a token in design/tokens.json.",
        )
    }
}
