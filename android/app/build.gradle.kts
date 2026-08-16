import groovy.json.JsonSlurper
import java.util.zip.ZipFile

plugins {
    alias(libs.plugins.android.application)
    // No kotlin-android plugin: AGP 9 has Kotlin support built in and rejects
    // it. See https://kotl.in/gradle/agp-built-in-kotlin
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "ai.raksha.app"
    // 37 is a floor, not a preference: androidx.core 1.19.0 and Compose 1.12.0
    // require dependents to compile against 37 or later.
    compileSdk = 37

    defaultConfig {
        applicationId = "ai.raksha.app"
        // Android 7.0. The users this is built for are on cheap, old handsets;
        // a higher floor would exclude exactly the people most targeted by
        // these scams.
        minSdk = 24
        // TARGET API DEADLINE (#82 §4).
        //
        // Play enforces a rolling minimum targetSdk: an app must target within
        // one year of the latest major Android release, or new uploads and
        // updates are rejected. Existing installs keep working, so the failure
        // arrives as a blocked release rather than a broken app - which is why
        // it is worth a calendar entry rather than a surprise.
        //
        // The rule is stable; the dates are not, and they are not written here
        // because a wrong date is worse than none. Confirm the current one in
        // Play Console -> Policy -> App content, or
        // developer.android.com/google/play/requirements/target-sdk, and put it
        // in the release checklist (#82 §7) so it is discovered on a date rather
        // than on a rejection.
        //
        // 37 is comfortably current today. The version that will force a bump is
        // whichever Android ships next, roughly a year ahead of the deadline.
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    // Release signing, read from the environment — never from a file in the
    // repo (#82 §1). `.gitignore` already covers *.jks and *.keystore, so this
    // is about there being no config that could tempt someone to add one.
    //
    // All four values must be present or the signing config is not created at
    // all, and `assembleRelease` produces an unsigned APK exactly as it does
    // today. That is deliberate: a half-configured signing setup that silently
    // signs with the wrong key is worse than one that obviously did not sign.
    // `verifyReleaseSigning` below turns "not signed" into a loud failure when
    // signing was actually intended.
    //
    // The #70 trap applies here — a secret is named in four places (GitHub
    // secret, workflow env block, this file, and the docs) and getting three
    // right fails in a way that looks like a keystore problem.
    val keystorePath = providers.environmentVariable("RAKSHA_KEYSTORE_PATH").orNull
    val keystorePassword = providers.environmentVariable("RAKSHA_KEYSTORE_PASSWORD").orNull
    val keyAlias = providers.environmentVariable("RAKSHA_KEY_ALIAS").orNull
    val keyPassword = providers.environmentVariable("RAKSHA_KEY_PASSWORD").orNull
    val hasSigningConfig =
        !keystorePath.isNullOrBlank() && !keystorePassword.isNullOrBlank() &&
            !keyAlias.isNullOrBlank() && !keyPassword.isNullOrBlank()

    if (hasSigningConfig) {
        signingConfigs {
            create("release") {
                storeFile = file(keystorePath!!)
                storePassword = keystorePassword
                this.keyAlias = keyAlias
                this.keyPassword = keyPassword
                // v1 (JAR signing) is off: it is only needed below API 24 and
                // minSdk is 24. Leaving it on is not free — it emitted a
                // META-INF/CERT.RSA that `apksigner verify` then reported as
                // "v1 scheme: false", i.e. a signature file present and not
                // valid, which is the most confusing possible state to debug.
                enableV1Signing = false
                enableV2Signing = true
                enableV3Signing = true
            }
        }
    }

    buildTypes {
        release {
            signingConfig = if (hasSigningConfig) signingConfigs.getByName("release") else null

            // R8 on. It was off through the shell phase, which was fine while
            // nothing shipped — but the release APK is what a pilot user
            // installs, and an unminified build hands anyone who pulls it a
            // readable map of the detection logic. The rules are not a secret,
            // yet making them trivially readable helps only the people writing
            // around them.
            //
            // Shrinking resources too: the generated per-language string
            // resources (see GenerateRuleStrings) grow with every language, and
            // the target handset is a cheap one where install size is a real
            // cost to a real person.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    // The on-device detection engine. Pure JVM, no Android dependencies —
    // see docs/RULE-PARITY.md.
    implementation(project(":core:rules"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.navigation.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.core)
    implementation(libs.androidx.compose.ui.tooling.preview)
    debugImplementation(libs.androidx.compose.ui.tooling)

    testImplementation(libs.junit4)
    testImplementation(libs.kotlin.test.junit)
}

// --- Rule labels, generated from the web app's translations -----------------
//
// #29 §1 is explicit that the app must consume the *same* translations the
// website uses rather than retyping them. Hand-copied strings drift: someone
// rewords a rule label on the web, the phone keeps the old wording, and the two
// products explain the same verdict differently.
//
// Source of truth: frontend/src/i18n/locales/<lang>.json
// Generated into:  build/generated/i18nRes/values[-<lang>]/rule_strings.xml
//
// This lives inline rather than in an applied script because an `apply(from =)`
// Kotlin script does not get AGP's typed accessors.

// Kept in sync with RULES in :core:rules. Duplicated deliberately: this runs
// before that module is compiled, so a build script cannot read it.
// RuleLabelsTest asserts the two agree.
val requiredRuleIds = listOf(
    "otp_share", "kyc_expiry", "lottery_win", "account_lock", "refund_click", "urgent_verify",
)

// Web locale code -> Android resource qualifier. Identity today, but stated
// explicitly because Urdu will need an RTL-aware qualifier and Odia needs
// `b+or` on older platforms.
val localeQualifiers = mapOf(
    "en" to "",  // default resources
    "hi" to "-hi",
    "gu" to "-gu",
)

// Android resource names that map to a web key outside the `android.*`
// namespace, because the string already existed there. `language_heading` was a
// verbatim duplicate of `common.language` in all three locales — aliasing is
// better than moving a second copy under `android.*` and having two keys that
// must be kept identical by hand.
val sharedStringAliases = mapOf(
    "language_heading" to listOf("common", "language"),
)

// Keys with no translation in a locale yet, so the build reports rather than
// fails. These are not new gaps: `rule_generic_warning` has been falling back to
// English on Hindi and Gujarati phones since #61, silently. Moving it into the
// bundles is what made that visible. Tracked in #52, which is open precisely
// because we have no native-speaker review capacity — and a machine
// translation of a scam warning is the failure i18n/index.ts warns about, so
// the honest state is "missing and named", not "filled in by whoever was here".
//
// Anything NOT on this list that goes missing fails the build.
// The eight call_* keys arrive untranslated with #116 §4, and that is a gap
// being *named* rather than one being accepted. A Hindi or Gujarati speaker on
// this build sees the call-screening feature entirely in English, which for the
// senior citizen THREAT-LANDSCAPE §02 designs for is close to not having it.
//
// They are not machine-translated, for the reason i18n/index.ts gives and #52
// records: a machine translation of a scam warning is worse than an English one,
// because it reads as authoritative while being wrong about the one sentence
// that has to be right. @Ayush3422 owns language and supplies these before the
// feature is claimed as shipped in any locale but English.
val callScreeningUntranslated = setOf(
    "call_warning_title",
    "call_screening_heading",
    "call_screening_on",
    "call_screening_off",
    "call_screening_enable",
    "call_screening_explainer",
    "call_screening_unsupported",
    "call_screening_nothing_known",
)

val knownUntranslated = mapOf(
    "hi" to setOf("rule_generic_warning") + callScreeningUntranslated,
    "gu" to setOf("rule_generic_warning") + callScreeningUntranslated,
)

abstract class GenerateRuleStrings : DefaultTask() {

    @get:InputDirectory
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val localesDir: DirectoryProperty

    @get:Input
    abstract val ruleIds: ListProperty<String>

    @get:Input
    abstract val localeToQualifier: MapProperty<String, String>

    /** Android resource name -> path to the web key, for strings that already
     * lived outside the `android.*` namespace. */
    @get:Input
    abstract val aliases: MapProperty<String, List<String>>

    /** locale -> resource names allowed to be absent, with #52 as the reason. */
    @get:Input
    abstract val allowedMissing: MapProperty<String, Set<String>>

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    private fun androidEscape(value: String): String =
        value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "\\'")
            .replace("\"", "\\\"")

    @Suppress("UNCHECKED_CAST")
    @TaskAction
    fun generate() {
        // This task reads outside the Gradle root, which is correct in the
        // monorepo and confusing anywhere else. Without this check a standalone
        // `android/` checkout fails with a bare path error from deep inside
        // JsonSlurper, and the reader has no way to know the directory is meant
        // to be there (#49).
        val locales = localesDir.get().asFile
        require(locales.isDirectory) {
            "Cannot find the web app's i18n bundles at ${locales.absolutePath}.\n" +
                "The Android build reads its rule labels straight from the web " +
                "translations so the two products cannot describe the same rule " +
                "differently (#29 §1), which means `android/` builds only inside a " +
                "full checkout of the repository — not on its own. If you copied " +
                "`android/` somewhere else, copy `frontend/src/i18n/locales/` with it."
        }

        val root = outputDir.get().asFile
        root.deleteRecursively()
        root.mkdirs()

        val ids = ruleIds.get()
        val missing = mutableListOf<String>()
        val englishSharedKeys = mutableListOf<String>()

        // English first, always. The other locales are checked against the key
        // set it defines, so processing them in map order would silently skip
        // the check for any locale that happened to come before `en`.
        val ordered = localeToQualifier.get().entries.sortedBy { if (it.key == "en") 0 else 1 }
        ordered.forEach { (locale, qualifier) ->
            val source = File(localesDir.get().asFile, "$locale.json")
            if (!source.isFile) {
                throw GradleException(
                    "i18n bundle missing: ${source.absolutePath}. The Android build reads the " +
                        "web app's translations directly and cannot proceed without them."
                )
            }

            val parsed = JsonSlurper().parse(source, "UTF-8") as Map<String, Any?>
            val trace = parsed["trace"] as? Map<String, Any?>
            val rules = trace?.get("rules") as? Map<String, Any?> ?: emptyMap()

            ids.forEach { id -> if (rules[id] == null) missing += "$locale/trace.rules.$id" }

            // Shared UI strings (#64). Every key under `android.*` becomes a
            // resource of the same name, so the Kotlin call sites do not change
            // and a reviewer can grep one name across both platforms.
            val shared = parsed["android"] as? Map<String, Any?> ?: emptyMap()

            // fold rather than a captured var: walking the key path by
            // reassigning a local inside a lambda is the kind of thing that
            // compiles on one Kotlin version and not the next.
            val resolvedAliases = aliases.get().mapNotNull { (resName, path) ->
                val value = path.fold(parsed as Any?) { node, segment ->
                    (node as? Map<*, *>)?.get(segment)
                }
                value?.let { resName to it.toString() }
            }.toMap()

            // English defines the contract; the other locales are checked
            // against it. A key present in one locale and absent from another is
            // exactly the drift #29 §1 asks CI to catch — except where #52 has
            // already named it.
            if (locale == "en") {
                englishSharedKeys.addAll(shared.keys.map { it.toString() })
            } else {
                val excused = allowedMissing.get()[locale].orEmpty()
                englishSharedKeys.forEach { key ->
                    if (shared[key] == null && key !in excused) missing += "$locale/android.$key"
                }
            }
            aliases.get().keys.forEach { resName ->
                if (resolvedAliases[resName] == null) missing += "$locale/${aliases.get()[resName]?.joinToString(".")}"
            }

            val valuesDir = File(root, "values$qualifier").apply { mkdirs() }
            val xml = buildString {
                appendLine("""<?xml version="1.0" encoding="utf-8"?>""")
                appendLine("<!-- GENERATED from frontend/src/i18n/locales/$locale.json - do not edit. -->")
                appendLine("<!-- Regenerate with: ./gradlew :app:assembleDebug -->")
                appendLine("<resources>")
                ids.forEach { id ->
                    val label = rules[id]?.toString() ?: return@forEach
                    appendLine("""    <string name="trace_rules_$id">${androidEscape(label)}</string>""")
                }
                (shared.keys.map { it.toString() } + resolvedAliases.keys).sorted().forEach { name ->
                    val value = shared[name]?.toString() ?: resolvedAliases[name] ?: return@forEach
                    appendLine("""    <string name="$name">${androidEscape(value)}</string>""")
                }
                appendLine("</resources>")
            }
            File(valuesDir, "rule_strings.xml").writeText(xml, Charsets.UTF_8)
        }

        // #29 §1: "CI fails on a key present in one platform and missing in the
        // other." Without this a new rule reaches the user as a raw regex.
        if (missing.isNotEmpty()) {
            throw GradleException(
                "Rule labels missing from the web i18n bundles: ${missing.joinToString(", ")}.\n" +
                    "Every rule id the engine can emit needs a trace.rules.<id> entry in every " +
                    "locale, or the app would show a raw pattern to a user. Add them to " +
                    "frontend/src/i18n/locales/ first - the web app needs them too."
            )
        }

        val excusedCount = allowedMissing.get().values.sumOf { it.size }
        logger.lifecycle(
            "Generated strings: ${localeToQualifier.get().size} locales x " +
                "(${ids.size} rules + ${englishSharedKeys.size} shared + ${aliases.get().size} aliased)"
        )
        if (excusedCount > 0) {
            logger.warn(
                "$excusedCount shared string(s) have no translation and fall back to English - see #52: " +
                    allowedMissing.get().entries.joinToString(", ") { (loc, keys) -> "$loc:${keys.joinToString("/")}" }
            )
        }
    }
}

// --- Design tokens, generated from design/tokens.json (#116 §2) --------------
//
// The web has had a brand palette since the beginning and this module rendered
// bare `MaterialTheme {}` — Material's default purple — so the two products did
// not look like the same company. Rather than hand-copying five hex values into
// Kotlin and letting them rot, the theme is generated from the same file the
// web side is checked against.
//
// Kotlin source rather than colors.xml: the values are consumed by Compose, and
// a generated `Color` is usable in a `@Composable` without a resource lookup.

abstract class GenerateDesignTokens : DefaultTask() {

    @get:InputFile
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val tokensFile: RegularFileProperty

    @get:OutputDirectory
    abstract val outputDir: DirectoryProperty

    /** `#rrggbb` -> `0xFFrrggbb`, the form Compose's Color(Long) wants. */
    private fun composeLiteral(hex: String): String {
        val cleaned = hex.removePrefix("#")
        require(cleaned.length == 6 && cleaned.all { it.isDigit() || it.lowercaseChar() in 'a'..'f' }) {
            "design/tokens.json has a colour that is not #rrggbb: '$hex'"
        }
        return "0xFF${cleaned.uppercase()}"
    }

    @Suppress("UNCHECKED_CAST")
    @TaskAction
    fun generate() {
        val file = tokensFile.get().asFile
        require(file.isFile) {
            "Cannot find design/tokens.json at ${file.absolutePath}. The Android theme is " +
                "generated from it so the phone and the site cannot drift (#116 §2), which " +
                "means `android/` builds only inside a full checkout of the repository."
        }

        val parsed = JsonSlurper().parse(file, "UTF-8") as Map<String, Any?>

        fun group(name: String): Map<String, Map<String, Any?>> =
            (parsed[name] as? Map<String, Any?> ?: emptyMap())
                .filterKeys { !it.startsWith("$") }
                .mapValues { (_, v) -> v as Map<String, Any?> }

        val brand = group("color")
        val verdict = group("verdict")
        require(brand.isNotEmpty()) { "design/tokens.json has no `color` entries" }
        require(verdict.isNotEmpty()) { "design/tokens.json has no `verdict` entries" }

        // Kotlin identifiers: verdict keys are snake_case in the JSON because
        // that is the wire format the backend uses for a verdict.
        fun camel(key: String) = key.split("_").mapIndexed { i, part ->
            if (i == 0) part else part.replaceFirstChar(Char::uppercase)
        }.joinToString("")

        val out = File(outputDir.get().asFile, "ai/raksha/app/ui")
        out.mkdirs()

        val text = buildString {
            appendLine("package ai.raksha.app.ui")
            appendLine()
            appendLine("import androidx.compose.ui.graphics.Color")
            appendLine()
            appendLine("/**")
            appendLine(" * GENERATED from design/tokens.json — do not edit.")
            appendLine(" *")
            appendLine(" * Regenerate with any Android build. The web side is checked against the")
            appendLine(" * same file by frontend/scripts/check-design-tokens.mjs, so a value changed")
            appendLine(" * in one place cannot ship in only one product (#116 §2).")
            appendLine(" */")
            appendLine("object DesignTokens {")
            appendLine()
            brand.forEach { (name, token) ->
                val description = token["description"]?.toString()
                if (description != null) appendLine("    /** $description */")
                appendLine("    val ${camel(name)} = Color(${composeLiteral(token.getValue("value").toString())})")
            }
            appendLine()
            appendLine("    /** Verdict semantics, identical to the web (#116 §2). */")
            appendLine("    object Verdict {")
            verdict.forEach { (name, token) ->
                appendLine("        val ${camel(name)} = Color(${composeLiteral(token.getValue("value").toString())})")
            }
            appendLine()
            appendLine("        /** Keyed by the backend's verdict string, so an unknown verdict is null rather than a guess. */")
            appendLine("        val byName: Map<String, Color> = mapOf(")
            verdict.keys.forEach { name -> appendLine("            \"$name\" to ${camel(name)},") }
            appendLine("        )")
            appendLine("    }")
            appendLine("}")
        }

        File(out, "DesignTokens.kt").writeText(text, Charsets.UTF_8)
        logger.lifecycle(
            "Generated design tokens: ${brand.size} brand colours, ${verdict.size} verdict colours"
        )
    }
}

// The Variant API, not `sourceSets.res.srcDir` — AGP 9 rejects a provider there,
// and this form carries the task dependency automatically.
androidComponents {
    onVariants { variant ->
        val task = tasks.register<GenerateRuleStrings>(
            "generate${variant.name.replaceFirstChar(Char::uppercase)}RuleStrings"
        ) {
            description = "Generates rule label string resources from the web i18n bundles"
            localesDir.set(rootProject.layout.projectDirectory.dir("../frontend/src/i18n/locales"))
            ruleIds.set(requiredRuleIds)
            localeToQualifier.set(localeQualifiers)
            aliases.set(sharedStringAliases)
            allowedMissing.set(knownUntranslated)
        }
        variant.sources.res?.addGeneratedSourceDirectory(task, GenerateRuleStrings::outputDir)

        val tokensTask = tasks.register<GenerateDesignTokens>(
            "generate${variant.name.replaceFirstChar(Char::uppercase)}DesignTokens"
        ) {
            description = "Generates the Compose colour tokens from design/tokens.json"
            tokensFile.set(rootProject.layout.projectDirectory.file("../design/tokens.json"))
        }
        variant.sources.java?.addGeneratedSourceDirectory(tokensTask, GenerateDesignTokens::outputDir)
    }
}

// --- Release signing verification (#82 §1) ----------------------------------
//
// `assembleRelease` succeeds whether or not signing was configured, which is
// how an unsigned APK reaches an upload attempt and fails there instead of
// here. This task makes the intent explicit: run it and an unsigned release is
// a build failure with a sentence explaining which variable is missing.
//
// Not wired into `assembleRelease` itself, because CI builds release
// deliberately unsigned to prove R8 does not break the build (#69) and that
// job has no secrets.
/**
 * Is the APK Signing Block (v2/v3) present?
 *
 * Located deterministically rather than by scanning a window off the end. The
 * first version of this check looked in the last 64 KB, on the reasoning that
 * the block "sits just before the central directory" — true, and the reason the
 * window is the wrong tool. The block's distance from EOF is the whole central
 * directory plus the EOCD, and a central directory grows with entry count. Once
 * it passes 64 KB a correctly signed APK reports as unsigned, which fails
 * loudly and safely but does it in the middle of cutting a release.
 *
 * The generated per-language string resources grow with every language added,
 * so entry count is going up, not down.
 *
 * Instead: find the EOCD, read the central directory's offset out of it, and
 * look at the sixteen bytes immediately before that offset. The magic sits at
 * the very end of the signing block, so it ends exactly where the central
 * directory begins. No window, no guess.
 *
 * Scanning backwards for the EOCD *is* bounded, and legitimately: the ZIP spec
 * caps the trailing comment at 0xFFFF bytes, so the record cannot be further
 * than 22 + 65535 from the end. That is a bound the format guarantees, unlike
 * the one this replaces.
 *
 * Still a smoke test, not verification. `apksigner verify --verbose` is the real
 * check and is in docs/RELEASE.md, because it needs build-tools on PATH and
 * confirms the signature validates rather than merely exists.
 *
 * Top-level rather than inlined: it is a pure function of the bytes and reads
 * better named. Note that a script-level function referenced from a task action
 * captures the script instance, which the configuration cache cannot serialise —
 * that cache is not enabled here (`gradle.properties`), and turning it on would
 * want this moved inside `doLast` as a local function.
 */
fun hasApkSigningBlock(bytes: ByteArray): Boolean {
    val magic = "APK Sig Block 42".toByteArray(Charsets.UTF_8)
    val eocdSignature = byteArrayOf(0x50, 0x4b, 0x05, 0x06)
    val eocdMinSize = 22

    if (bytes.size < eocdMinSize) return false

    // Backwards, because a ZIP can legally contain the EOCD signature inside an
    // entry; the last occurrence is the real one.
    val searchFloor = maxOf(0, bytes.size - (eocdMinSize + 0xFFFF))
    var eocd = -1
    for (i in bytes.size - eocdMinSize downTo searchFloor) {
        if (eocdSignature.indices.all { bytes[i + it] == eocdSignature[it] }) {
            eocd = i
            break
        }
    }
    if (eocd < 0) return false

    // Central directory offset: 4 bytes, little-endian, at EOCD + 16.
    val cdOffset = (0..3).fold(0L) { acc, i ->
        acc or ((bytes[eocd + 16 + i].toLong() and 0xFF) shl (8 * i))
    }

    // 0xFFFFFFFF means the real offset lives in a ZIP64 record. Not handled,
    // and saying so beats reporting "unsigned" for a reason unrelated to
    // signing — an APK that large is not a situation this project has.
    if (cdOffset == 0xFFFFFFFFL) {
        throw GradleException(
            "This APK uses ZIP64, which this check does not read. Verify it with " +
                "`apksigner verify --verbose` instead - see docs/RELEASE.md."
        )
    }
    if (cdOffset < magic.size || cdOffset > bytes.size) return false

    val magicStart = (cdOffset - magic.size).toInt()
    return magic.indices.all { bytes[magicStart + it] == magic[it] }
}

tasks.register("verifyReleaseSigning") {
    group = "verification"
    description = "Fails unless the release APK is signed (see #82 §1)"

    val apkDir = layout.buildDirectory.dir("outputs/apk/release")
    val required = listOf(
        "RAKSHA_KEYSTORE_PATH",
        "RAKSHA_KEYSTORE_PASSWORD",
        "RAKSHA_KEY_ALIAS",
        "RAKSHA_KEY_PASSWORD",
    )
    val present = required.associateWith { providers.environmentVariable(it).orNull }

    doLast {
        val missing = present.filterValues { it.isNullOrBlank() }.keys
        if (missing.isNotEmpty()) {
            throw GradleException(
                "Release signing is not configured: ${missing.joinToString(", ")} " +
                    "${if (missing.size == 1) "is" else "are"} unset.\n" +
                    "An unsigned APK cannot be uploaded to Play. Set all four, or " +
                    "build debug if you did not mean to produce a release artifact.\n" +
                    "Setup and the full release path are in docs/RELEASE.md."
            )
        }

        val apks = apkDir.get().asFile.listFiles { f -> f.extension == "apk" }.orEmpty()
        if (apks.isEmpty()) {
            throw GradleException(
                "No release APK found in ${apkDir.get().asFile}. Run assembleRelease first."
            )
        }
        // Looks for the APK Signing Block (v2/v3), not META-INF/*.RSA.
        //
        // The META-INF check was the first attempt and it is wrong in both
        // directions: v1 is disabled at minSdk 24, so a correctly signed APK
        // has no .RSA entry and would be reported unsigned; and a stale .RSA
        // can survive from an earlier config while the signature does not
        // actually verify. The signing block's magic string is what v2 and v3
        // both write, and it is absent from an unsigned APK.
        //
        // This is a smoke test, not verification. `apksigner verify` is the
        // real check and needs build-tools on PATH:
        //   apksigner verify --verbose app-release.apk
        // That belongs in the release checklist (#82 §7, @CODER7657).
        apks.forEach { apk ->
            val signed = apk.readBytes().let { bytes -> hasApkSigningBlock(bytes) }
            if (!signed) {
                throw GradleException(
                    "${apk.name} has no signature block, even though all four " +
                        "signing variables are set.\n" +
                        "Two causes, in order of likelihood:\n" +
                        "  1. A stale artifact from an earlier unsigned build is " +
                        "still in outputs/apk/release. `assembleRelease` reports " +
                        "UP-TO-DATE and never re-signs it. Run `clean` first - a " +
                        "leftover *-unsigned.apk sitting next to a signed one is " +
                        "also exactly the file someone uploads by mistake.\n" +
                        "  2. The variables reached the shell but not the Gradle " +
                        "process - check the daemon was not already running with " +
                        "the old environment (`--no-daemon` to rule it out)."
                )
            }
        }
        logger.lifecycle("Release APK signature present: ${apks.joinToString { it.name }}")
    }
}

// --- Files the unit tests read that Gradle could not see --------------------
//
// #125. Three tests in this module read files directly from disk, and none of
// them was a declared input, so the cache key never covered them. A test task
// can then be served from cache across a change to the very thing it checks —
// reporting success without executing an assertion, which is worse than having
// no check because people believe it.
//
// This is the same defect that let the rule-engine parity gate pass for months
// while the Kotlin engine diverged from the corpus on 13 cases. It is fixed on
// :core:rules:test in the same commit; these are the rest of it.
//
//   SharedStringCoverageTest  src/main/res/values*/strings.xml  (#71, #80)
//                             ../../frontend/src/i18n/locales   (#64, #99)
//   DesignTokensTest          design/tokens.json                (#116 §2, #118)
//
// The second and third read outside the Gradle root, which is correct in this
// monorepo: both exist precisely to stop the web and the phone drifting, so the
// file they compare against necessarily lives on the other side of the seam.
//
// Severity differs and is worth recording rather than flattening. The i18n keys
// have a second enforcer — GenerateRuleStrings throws inside assembleDebug on a
// missing key — so a cached test there hid less. The shadowing guard #80 turned
// on has no backstop at all, and neither does the token check, whose whole
// subject is a generated file being stale: a cached pass is exactly the failure
// it was written to catch.
tasks.withType<Test>().configureEach {
    inputs.dir(layout.projectDirectory.dir("src/main/res"))
        .withPropertyName("androidResources")
        .withPathSensitivity(PathSensitivity.RELATIVE)

    inputs.dir(rootProject.file("../frontend/src/i18n/locales"))
        .withPropertyName("webLocaleBundles")
        .withPathSensitivity(PathSensitivity.RELATIVE)

    inputs.file(rootProject.file("../design/tokens.json"))
        .withPropertyName("designTokens")
        .withPathSensitivity(PathSensitivity.RELATIVE)
}
