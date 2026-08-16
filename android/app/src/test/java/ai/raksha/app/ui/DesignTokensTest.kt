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

    @Test
    fun `every colour role comes from a token`() {
        // Setting `primary` and `background` alone was the first attempt, and it
        // left the selected FilterChip lavender because `secondaryContainer`
        // still came from Material's tonal palette. The page was cream and one
        // control was purple, which reads as a bug.
        //
        // Rather than list the roles that happened to be wrong, this asserts the
        // whole scheme: every role the app can render must be one of the brand
        // colours. A future control using a role nobody thought about fails here
        // instead of shipping off-brand.
        val brand = (colours("color") + colours("verdict")).values.toSet()

        val scheme = RakshaColorScheme
        val roles = mapOf(
            "primary" to scheme.primary,
            "onPrimary" to scheme.onPrimary,
            "primaryContainer" to scheme.primaryContainer,
            "onPrimaryContainer" to scheme.onPrimaryContainer,
            "secondary" to scheme.secondary,
            "onSecondary" to scheme.onSecondary,
            "secondaryContainer" to scheme.secondaryContainer,
            "onSecondaryContainer" to scheme.onSecondaryContainer,
            "tertiary" to scheme.tertiary,
            "onTertiary" to scheme.onTertiary,
            "tertiaryContainer" to scheme.tertiaryContainer,
            "onTertiaryContainer" to scheme.onTertiaryContainer,
            "background" to scheme.background,
            "onBackground" to scheme.onBackground,
            "surface" to scheme.surface,
            "onSurface" to scheme.onSurface,
            "surfaceVariant" to scheme.surfaceVariant,
            "onSurfaceVariant" to scheme.onSurfaceVariant,
            "outline" to scheme.outline,
            "outlineVariant" to scheme.outlineVariant,
            "error" to scheme.error,
            "onError" to scheme.onError,
            "errorContainer" to scheme.errorContainer,
            "onErrorContainer" to scheme.onErrorContainer,
        )

        val offBrand = roles.filterValues { hexOf(it) !in brand }.keys
        assertTrue(
            offBrand.isEmpty(),
            "these colour roles are not brand tokens and will render a Material " +
                "default: $offBrand. Map each to a token in design/tokens.json.",
        )
    }
}
