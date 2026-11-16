plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "io.github.horiidonuts.manbo"
    compileSdk = 37

    defaultConfig {
        applicationId = "io.github.horiidonuts.manbo"
        minSdk = 31
        targetSdk = 37
        versionCode = 1
        versionName = "0.2.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"))
            // signed with the debug key for now (sideloading); a real key comes with a store release
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    buildFeatures {
        compose = true
    }

    // the sound files live in ../data/sounds (not in git, see NOTICE); copied in at build time
    sourceSets["main"].res.directories.add(layout.buildDirectory.dir("generated/manboSounds").get().asFile.path)
}

// Copy the sounds the app uses from data/sounds into res/raw. Missing files are
// fine: the app then stays silent for those (like the desktop version).
val copySounds by tasks.registering(Copy::class) {
    from(rootProject.file("../data/sounds")) {
        include("button_press_2.*", "button_pop_up_2.*", "change_tab.*", "chime1.*")
    }
    into(layout.buildDirectory.dir("generated/manboSounds/raw"))
}
tasks.named("preBuild") { dependsOn(copySounds) }

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.09.00")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.11.0")
}
