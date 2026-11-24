package io.github.horiidonuts.manbo

import java.util.Locale

/**
 * Manbo speaks English and Turkish. Settings → Language picks one; "system" follows the phone.
 * The texts sit right where they're used, English first: t("Pause", "Duraklat").
 */
object Lang {
    val LANGUAGES = listOf("system", "en", "tr")

    val turkish: Boolean
        get() = when (SettingsStore.value.language) {
            "tr" -> true
            "en" -> false
            else -> Locale.getDefault().language == "tr"
        }

    val locale: Locale get() = if (turkish) Locale.forLanguageTag("tr") else Locale.ENGLISH
}

/** The text in the app's language. */
fun t(en: String, tr: String) = if (Lang.turkish) tr else en
