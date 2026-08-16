plugins {
    alias(libs.plugins.kotlin.jvm)
}

// Deliberately a plain JVM module, not an Android library:
//   - the suite runs on the JVM in seconds, with no emulator
//   - the bank-side embedded SDK can take this without dragging in our app
// If an `android` block ever appears here, that property has been lost.

kotlin {
    jvmToolchain(17)
}

dependencies {
    testImplementation(kotlin("test"))
    // Test-only: reads the shared corpus. The main source set has no
    // dependencies, and should stay that way.
    testImplementation(libs.kotlinx.serialization.json)
}

tasks.test {
    useJUnitPlatform()

    // THE SPECIFICATION IS AN INPUT. Without this line the parity gate cannot
    // fail (#125).
    //
    // RuleCorpusTest finds testdata/rule_corpus.jsonl by walking up from
    // `user.dir` at *runtime*, which Gradle cannot see. So the cache key covered
    // the compiled classes and the classpath and not the specification under
    // test — and since RuleEngine.kt had not changed since #42, every run after
    // that was served from cache. The step reported success without executing an
    // assertion, on every commit, for months.
    //
    // Measured before the fix, on master, with a deliberately impossible case
    // appended to the corpus (expect otp_share on the text "this sentence fires
    // nothing at all"):
    //
    //     > Task :core:rules:test FROM-CACHE
    //     BUILD SUCCESSFUL in 1s
    //
    // The gate accepted a specification it could not satisfy. What it was hiding
    // was 13 enforced cases the Kotlin engine diverges on — the phone being the
    // only detector on the SMS path, with no server fallback.
    //
    // This is the #22 lesson one layer down: not a check that passes when it
    // should fail, but a check nobody noticed was never being asked. Declaring
    // the file here is what makes the answer earned rather than remembered.
    inputs.file(rootProject.file("../testdata/rule_corpus.jsonl"))
        .withPropertyName("ruleCorpus")
        .withPathSensitivity(PathSensitivity.RELATIVE)

    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
