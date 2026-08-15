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
    testLogging {
        events("failed")
        exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL
    }
}
