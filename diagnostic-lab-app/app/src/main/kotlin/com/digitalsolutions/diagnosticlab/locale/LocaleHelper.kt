package com.digitalsolutions.diagnosticlab.locale

import android.content.Context
import android.content.res.Configuration
import java.util.Locale

/**
 * Applies the saved language preference at process start, before Compose (and its
 * stringResource() calls) ever runs. [SessionManager] is the source of truth for the
 * preference (DataStore, async); this mirrors just the language tag into a plain
 * SharedPreferences file so it can be read synchronously in Activity.attachBaseContext,
 * where a suspend DataStore read isn't an option.
 */
object LocaleHelper {
    private const val PREFS = "locale_prefs"
    private const val KEY_LANG = "lang"

    fun persist(context: Context, languageTag: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_LANG, languageTag).apply()
    }

    fun wrap(context: Context): Context {
        val tag = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_LANG, "en") ?: "en"
        val locale = Locale(tag)
        Locale.setDefault(locale)
        val config = Configuration(context.resources.configuration)
        config.setLocale(locale)
        return context.createConfigurationContext(config)
    }
}
