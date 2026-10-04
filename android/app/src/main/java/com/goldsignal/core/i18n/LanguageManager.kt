package com.goldsignal.core.i18n

import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

/** Per-app language (Android 13+ system setting; AppCompat back-port below that). */
object LanguageManager {
    val supported = listOf("en", "tr", "ru")

    /** "" = follow the system language. */
    fun current(): String = AppCompatDelegate.getApplicationLocales().toLanguageTags().substringBefore('-')

    fun set(tag: String) {
        val locales = if (tag.isEmpty()) LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(tag)
        AppCompatDelegate.setApplicationLocales(locales)
    }
}
