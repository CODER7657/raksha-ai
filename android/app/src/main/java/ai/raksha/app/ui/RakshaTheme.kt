package ai.raksha.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

/**
 * The app's Material 3 theme, built from the shared design tokens.
 *
 * Until #116 §2 this screen ran on a bare `MaterialTheme {}`, which meant
 * Material's default purple: the website had a brand and the phone did not, and
 * the two did not look like the same product. The colours here come from
 * [DesignTokens], generated from `design/tokens.json` — the same file the web
 * side is checked against — so neither platform can be re-tinted alone.
 *
 * **Light only, deliberately.** No dark scheme is defined yet rather than one
 * being guessed: the palette is a paper-and-ink brand with a single warm accent,
 * and inverting it mechanically produces contrast pairs nobody has checked
 * against the 4.5:1 floor the accessibility work requires. A dark scheme is
 * worth having and worth designing, not deriving. Until then the light scheme
 * is used regardless of system setting, which is honest rather than broken.
 */
@Composable
fun RakshaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = RakshaColorScheme,
        content = content,
    )
}

/**
 * Brand tokens mapped onto Material 3's roles.
 *
 * The mapping is the part worth reviewing, since the tokens themselves are
 * generated:
 *
 *  - `primary` is the accent, so every default-styled button is the brand's
 *    orange rather than purple.
 *  - `error`/`errorContainer` are the high-risk verdict colour, because the one
 *    place this app uses Material's error role is the "warnings cannot reach
 *    you" card (#49) — a fault the user must act on, which is the same
 *    seriousness the site paints high_risk with.
 *  - `surface` and `background` are paper, `onSurface` is ink, so the app reads
 *    as the same document the website does.
 *
 * **The container roles have to be set explicitly.** Leaving them out is what
 * the first version of this did, and Material fell back to its own tonal
 * palette for them — so the page went cream while the selected language chip
 * stayed lavender, which looks like a bug rather than a brand. Anything using
 * `secondaryContainer` or `errorContainer` needs a value here:
 *
 *  - `secondaryContainer` is `line`, the palette's neutral, used by the
 *    selected `FilterChip` and by the force-stop notice card (#93).
 *  - `errorContainer` is the high-risk verdict colour with white on it, which
 *    is exactly how the website paints a `high_risk` badge — so the
 *    "warnings cannot reach you" card (#49) reads with the same seriousness on
 *    both, rather than one shouting and the other murmuring.
 *
 * No new colours are invented here: every role maps to a token that already
 * existed. A tonal palette derived from a saturated orange lands on containers
 * nobody has checked against the 4.5:1 floor, and guessing one would be a
 * design decision made by a build script.
 */
internal val RakshaColorScheme = lightColorScheme(
    primary = DesignTokens.accent,
    onPrimary = DesignTokens.accentInk,
    primaryContainer = DesignTokens.accent,
    onPrimaryContainer = DesignTokens.accentInk,
    secondary = DesignTokens.ink,
    onSecondary = DesignTokens.paper,
    secondaryContainer = DesignTokens.line,
    onSecondaryContainer = DesignTokens.ink,
    tertiary = DesignTokens.ink,
    onTertiary = DesignTokens.paper,
    tertiaryContainer = DesignTokens.line,
    onTertiaryContainer = DesignTokens.ink,
    background = DesignTokens.paper,
    onBackground = DesignTokens.ink,
    surface = DesignTokens.paper,
    onSurface = DesignTokens.ink,
    surfaceVariant = DesignTokens.line,
    onSurfaceVariant = DesignTokens.ink,
    outline = DesignTokens.line,
    outlineVariant = DesignTokens.line,
    error = DesignTokens.Verdict.highRisk,
    onError = DesignTokens.accentInk,
    errorContainer = DesignTokens.Verdict.highRisk,
    onErrorContainer = DesignTokens.accentInk,
)
