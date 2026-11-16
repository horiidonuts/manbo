buildscript {
    // AGP 9 has Kotlin built in (2.2.x); use a newer Kotlin to match the Compose compiler plugin
    dependencies {
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:2.4.21")
    }
}

plugins {
    id("com.android.application") version "9.5.1" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.4.21" apply false
}
