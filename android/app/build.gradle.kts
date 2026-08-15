import groovy.json.JsonSlurper

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
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
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

abstract class GenerateRuleStrings : DefaultTask() {

    @get:InputDirectory
    @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val localesDir: DirectoryProperty

    @get:Input
    abstract val ruleIds: ListProperty<String>

    @get:Input
    abstract val localeToQualifier: MapProperty<String, String>

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
        val root = outputDir.get().asFile
        root.deleteRecursively()
        root.mkdirs()

        val ids = ruleIds.get()
        val missing = mutableListOf<String>()

        localeToQualifier.get().forEach { (locale, qualifier) ->
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

        logger.lifecycle("Generated rule labels: ${localeToQualifier.get().size} locales x ${ids.size} rules")
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
        }
        variant.sources.res?.addGeneratedSourceDirectory(task, GenerateRuleStrings::outputDir)
    }
}
