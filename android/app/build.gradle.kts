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
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui.tooling.preview)
    debugImplementation(libs.androidx.compose.ui.tooling)
}
