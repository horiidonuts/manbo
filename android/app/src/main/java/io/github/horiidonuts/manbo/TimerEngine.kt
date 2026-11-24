package io.github.horiidonuts.manbo

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlin.math.ceil
import kotlin.math.max

enum class Mode(val key: String, private val en: String, private val tr: String) {
    FOCUS("focus", "Focus", "Odak"),
    SHORT("short", "Short break", "Kısa mola"),
    LONG("long", "Long break", "Uzun mola");

    val label get() = t(en, tr)
    val title get() = label.uppercase(Lang.locale)

    companion object {
        fun of(key: String?) = entries.firstOrNull { it.key == key } ?: FOCUS
    }
}

/**
 * The Pomodoro state. Uses the wall clock for the end time (like the desktop
 * D-Bus API's endTime), so it survives the app being killed and can later be
 * synced between devices.
 */
data class TimerState(
    val mode: Mode = Mode.FOCUS,
    val running: Boolean = false,
    val endAt: Long = 0,              // wall clock ms when the session ends (running only)
    val remainingMs: Long = 25 * 60_000L, // while not running
    val started: Boolean = false,     // has this session been started at all?
    val completed: Int = 0,           // finished focus sessions
    val version: Long = 0,            // +1 on every change
    // PC sync: when (wall clock ms) and on which device the last user action happened; newest wins
    val stamp: Long = 0,
    val by: String = "",
) {
    fun remainingMs(now: Long = System.currentTimeMillis()) =
        if (running) max(0L, endAt - now) else remainingMs

    fun remainingSeconds(now: Long = System.currentTimeMillis()) =
        ceil(remainingMs(now) / 1000.0).toInt()

    fun cyclePosition(interval: Int) = if (mode == Mode.LONG) interval else completed % interval
}

data class Finished(val finished: Mode, val next: Mode)

object TimerEngine {
    private lateinit var app: Context
    private lateinit var prefs: SharedPreferences
    private val _state = MutableStateFlow(TimerState())
    val state: StateFlow<TimerState> = _state
    val value get() = _state.value

    /** A session ended (UI: pop the button, play the chime, hand off to the next session). */
    private val _finished = MutableSharedFlow<Finished>(extraBufferCapacity = 4)
    val finished: SharedFlow<Finished> = _finished

    fun init(context: Context) {
        if (::prefs.isInitialized) return
        app = context.applicationContext
        SettingsStore.init(app)
        HistoryStore.init(app)
        prefs = app.getSharedPreferences("timer", Context.MODE_PRIVATE)
        val mode = Mode.of(prefs.getString("mode", null))
        _state.value = TimerState(
            mode = mode,
            running = prefs.getBoolean("running", false),
            endAt = prefs.getLong("end_at", 0),
            remainingMs = prefs.getLong("remaining_ms", duration(mode)),
            started = prefs.getBoolean("started", false),
            completed = prefs.getInt("completed", 0),
            version = prefs.getLong("version", 0),
            stamp = prefs.getLong("stamp", 0),
            by = prefs.getString("by", "") ?: "",
        )
        finishIfDue()
    }

    private fun duration(mode: Mode) = SettingsStore.value.minutes(mode) * 60_000L

    // -- actions ---------------------------------------------------------------

    fun start() {
        val s = touch(value)
        if (s.running) return
        set(s.copy(running = true, started = true, endAt = s.stamp + s.remainingMs))
    }

    fun pause() {
        val s = touch(value)
        if (!s.running) return
        set(s.copy(running = false, remainingMs = s.remainingMs(), endAt = 0))
    }

    fun toggle() = if (value.running) pause() else start()

    fun reset() = set(enter(touch(value), value.mode))

    /** Manually switch to [mode]: stops the timer and starts that session fresh. */
    fun select(mode: Mode) {
        if (mode == value.mode && !value.started) return
        set(enter(touch(value), mode))
    }

    /** Take over the PC's (newer) state. */
    fun applyRemote(s: TimerState) = set(s.copy(version = value.version))

    /** After a reboot: the alarm and the countdown notification are gone, put them back. */
    fun restore() {
        finishIfDue()
        scheduleAlarm(value)
        Notifications.updateOngoing(app, value)
    }

    /** Durations changed in settings: an untouched session picks up the new length. */
    fun onSettingsChanged() {
        val s = value
        if (!s.started && s.remainingMs != duration(s.mode)) set(s.copy(remainingMs = duration(s.mode)))
        else set(s, bump = false)
    }

    /** Called from the alarm and whenever the app comes back: end the session if its time is up. */
    fun finishIfDue(force: Boolean = false) {
        val s = value
        if (!s.running || (!force && System.currentTimeMillis() < s.endAt)) return
        val finished = s.mode
        val completed = if (finished == Mode.FOCUS) s.completed + 1 else s.completed
        val interval = SettingsStore.value.longBreakInterval
        val next = when {
            finished != Mode.FOCUS -> Mode.FOCUS
            completed > 0 && completed % interval == 0 -> Mode.LONG
            else -> Mode.SHORT
        }
        // every device ends a session the same way at the same moment, so they agree
        set(enter(s.copy(completed = completed, stamp = s.endAt), next))
        if (finished == Mode.FOCUS) HistoryStore.record(s.endAt, SettingsStore.value.focusMinutes)   // a new star
        _finished.tryEmit(Finished(finished, next))
        SessionEnd.onFinished(app, finished, next)
    }

    // -- internals -------------------------------------------------------------

    private fun enter(s: TimerState, mode: Mode) =
        s.copy(mode = mode, running = false, started = false, endAt = 0, remainingMs = duration(mode))

    private fun touch(s: TimerState) = s.copy(stamp = System.currentTimeMillis(), by = SyncStore.me)

    private fun set(s: TimerState, bump: Boolean = true) {
        val next = if (bump) s.copy(version = value.version + 1) else s
        _state.value = next
        prefs.edit()
            .putString("mode", next.mode.key)
            .putBoolean("running", next.running)
            .putLong("end_at", next.endAt)
            .putLong("remaining_ms", next.remainingMs)
            .putBoolean("started", next.started)
            .putInt("completed", next.completed)
            .putLong("version", next.version)
            .putLong("stamp", next.stamp)
            .putString("by", next.by)
            .apply()
        scheduleAlarm(next)
        Notifications.updateOngoing(app, next)
        Dnd.update(app, next)
    }

    private fun alarmIntent() = PendingIntent.getBroadcast(
        app, 0, Intent(app, AlarmReceiver::class.java),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
    )

    private fun scheduleAlarm(s: TimerState) {
        val alarms = app.getSystemService(AlarmManager::class.java)
        if (s.running) {
            alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, s.endAt, alarmIntent())
        } else {
            alarms.cancel(alarmIntent())
        }
    }
}
