import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

// Release signing key, kept outside the repo. Point MANBO_KEYSTORE at a keystore.properties
// (storeFile, storePassword, keyAlias, keyPassword); without one, release builds use the debug key.
val keystoreProps = (System.getenv("MANBO_KEYSTORE")
    ?: "${System.getProperty("user.home")}/.local/share/manbo-signing/keystore.properties")
    .let(::File).takeIf { it.isFile }
    ?.let { f -> Properties().apply { f.inputStream().use(::load) } }

android {
    namespace = "io.github.horiidonuts.manbo"
    compileSdk = 37

    defaultConfig {
        applicationId = "io.github.horiidonuts.manbo"
        minSdk = 26
        targetSdk = 37
        versionCode = 7
        versionName = "0.6.0"
    }

    signingConfigs {
        if (keystoreProps != null) create("release") {
            storeFile = file(keystoreProps.getProperty("storeFile"))
            storePassword = keystoreProps.getProperty("storePassword")
            keyAlias = keystoreProps.getProperty("keyAlias")
            keyPassword = keystoreProps.getProperty("keyPassword")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
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
    testImplementation("junit:junit:4.13.2")
    // "Scan code" for pairing with the PC: Google's scanner UI, no camera permission needed
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
    implementation("androidx.fragment:fragment:1.9.1")   // the scanner pulls in an old one
}
