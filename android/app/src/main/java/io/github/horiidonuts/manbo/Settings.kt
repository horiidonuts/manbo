package io.github.horiidonuts.manbo

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** Same settings as the desktop app (manbo/settings.py), kept in SharedPreferences. */
data class Settings(
    val focusMinutes: Int = 25,
    val shortBreakMinutes: Int = 5,
    val longBreakMinutes: Int = 15,
    val longBreakInterval: Int = 4,
    val theme: String = "blossom",
    val buttonSounds: Boolean = true,
    val chimeLength: String = "normal",   // off / short / normal / long
    val chimeVolume: Int = 80,
    val rollingDigits: Boolean = true,
    val dndDuringFocus: Boolean = false,
    val syncInBackground: Boolean = true,   // stay connected to the paired PC while closed
    val language: String = "system",        // system / en / tr (Strings.kt)
    // when / on which device the durations last changed (they sync with the PC; newest wins)
    val durStamp: Long = 0,
    val durBy: String = "",
) {
    fun sameDurations(o: Settings) = focusMinutes == o.focusMinutes && shortBreakMinutes == o.shortBreakMinutes &&
        longBreakMinutes == o.longBreakMinutes && longBreakInterval == o.longBreakInterval

    fun minutes(mode: Mode) = when (mode) {
        Mode.FOCUS -> focusMinutes
        Mode.SHORT -> shortBreakMinutes
        Mode.LONG -> longBreakMinutes
    }

    companion object {
        val RANGES = mapOf(
            "focusMinutes" to 1..180,
            "shortBreakMinutes" to 1..60,
            "longBreakMinutes" to 1..120,
            "longBreakInterval" to 1..12,
        )
        val CHIME_LENGTHS = listOf("off", "short", "normal", "long")
        // where the chime starts (ms), tuned for chime1 like the desktop app
        val CHIME_STARTS = mapOf("short" to 3950, "normal" to 2000, "long" to 0)
    }
}

object SettingsStore {
    private lateinit var prefs: SharedPreferences
    private val _state = MutableStateFlow(Settings())
    val state: StateFlow<Settings> = _state
    val value get() = _state.value

    fun init(context: Context) {
        if (::prefs.isInitialized) return
        SyncStore.init(context)
        prefs = context.applicationContext.getSharedPreferences("settings", Context.MODE_PRIVATE)
        val d = Settings()
        _state.value = Settings(
            focusMinutes = prefs.getInt("focus_minutes", d.focusMinutes),
            shortBreakMinutes = prefs.getInt("short_break_minutes", d.shortBreakMinutes),
            longBreakMinutes = prefs.getInt("long_break_minutes", d.longBreakMinutes),
            longBreakInterval = prefs.getInt("long_break_interval", d.longBreakInterval),
            theme = prefs.getString("theme", d.theme) ?: d.theme,
            buttonSounds = prefs.getBoolean("button_sounds", d.buttonSounds),
            chimeLength = prefs.getString("chime_length", d.chimeLength) ?: d.chimeLength,
            chimeVolume = prefs.getInt("chime_volume", d.chimeVolume),
            rollingDigits = prefs.getBoolean("rolling_digits", d.rollingDigits),
            dndDuringFocus = prefs.getBoolean("dnd_during_focus", d.dndDuringFocus),
            syncInBackground = prefs.getBoolean("sync_background", d.syncInBackground),
            language = prefs.getString("language", d.language) ?: d.language,
            durStamp = prefs.getLong("durations_stamp", 0),
            durBy = prefs.getString("durations_by", "") ?: "",
        )
    }

    fun update(change: (Settings) -> Settings) {
        val old = _state.value
        var s = change(old)
        // changed here (not taken over from the PC): stamp it so it wins over older changes there
        if (!s.sameDurations(old) && s.durStamp == old.durStamp) {
            s = s.copy(durStamp = System.currentTimeMillis(), durBy = SyncStore.me)
        }
        _state.value = s
        prefs.edit()
            .putInt("focus_minutes", s.focusMinutes)
            .putInt("short_break_minutes", s.shortBreakMinutes)
            .putInt("long_break_minutes", s.longBreakMinutes)
            .putInt("long_break_interval", s.longBreakInterval)
            .putString("theme", s.theme)
            .putBoolean("button_sounds", s.buttonSounds)
            .putString("chime_length", s.chimeLength)
            .putInt("chime_volume", s.chimeVolume)
            .putBoolean("rolling_digits", s.rollingDigits)
            .putBoolean("dnd_during_focus", s.dndDuringFocus)
            .putBoolean("sync_background", s.syncInBackground)
            .putString("language", s.language)
            .putLong("durations_stamp", s.durStamp)
            .putString("durations_by", s.durBy)
            .apply()
    }
}
