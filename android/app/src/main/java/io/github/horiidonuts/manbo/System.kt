package io.github.horiidonuts.manbo

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.media.SoundPool
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import java.text.DateFormat
import java.util.Date

/** Is the main screen showing? (Then the screen itself chimes, no notification.) */
object AppVisibility {
    @Volatile var visible = false
}

/** Raw resource id by name, or 0 when that sound file wasn't there at build time. */
fun rawId(context: Context, name: String): Int =
    context.resources.getIdentifier(name, "raw", context.packageName)

// -- alarm + notification actions ------------------------------------------------

class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        TimerEngine.init(context)
        TimerEngine.finishIfDue()
    }
}

class ActionReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        TimerEngine.init(context)
        when (intent.action) {
            ACTION_TOGGLE -> TimerEngine.toggle()
        }
    }

    companion object {
        const val ACTION_TOGGLE = "io.github.horiidonuts.manbo.TOGGLE"
    }
}

// -- notifications -------------------------------------------------------------------

object Notifications {
    private const val CH_TIMER = "timer"
    private const val CH_END = "session_end"
    private const val ID_ONGOING = 1
    const val ID_END = 2

    fun createChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_TIMER, "Running timer", NotificationManager.IMPORTANCE_LOW).apply {
            description = "The countdown while a session runs"
            setShowBadge(false)
        })
        nm.createNotificationChannel(NotificationChannel(CH_END, "Session finished", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "When a focus session or break is over"
            val chime = rawId(context, "chime1")
            if (chime != 0) {
                setSound(
                    Uri.parse("${ContentResolver.SCHEME_ANDROID_RESOURCE}://${context.packageName}/$chime"),
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build(),
                )
            }
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 120, 80, 120)
        })
    }

    private fun canPost(context: Context) =
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private fun openApp(context: Context) = PendingIntent.getActivity(
        context, 0, Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
        PendingIntent.FLAG_IMMUTABLE,
    )

    private fun toggleAction(context: Context) = PendingIntent.getBroadcast(
        context, 1, Intent(context, ActionReceiver::class.java).setAction(ActionReceiver.ACTION_TOGGLE),
        PendingIntent.FLAG_IMMUTABLE,
    )

    /** While a session runs: an ongoing countdown (a Live Update / Now Bar where supported). */
    fun updateOngoing(context: Context, s: TimerState) {
        val nm = NotificationManagerCompat.from(context)
        if (!s.running) {
            nm.cancel(ID_ONGOING)
            return
        }
        if (!canPost(context)) return
        val endsAt = DateFormat.getTimeInstance(DateFormat.SHORT).format(Date(s.endAt))
        val n = NotificationCompat.Builder(context, CH_TIMER)
            .setSmallIcon(R.drawable.ic_stat_manbo)
            .setContentTitle(s.mode.label)
            .setContentText("Ends at $endsAt")
            .setWhen(s.endAt)
            .setShowWhen(true)
            .setUsesChronometer(true)
            .setChronometerCountDown(true)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setSilent(true)
            .setCategory(Notification.CATEGORY_STOPWATCH)
            .setRequestPromotedOngoing(true)
            .setContentIntent(openApp(context))
            .addAction(0, "Pause", toggleAction(context))
            .build()
        nm.notify(ID_ONGOING, n)
    }

    /** A session ended while the app wasn't on screen. */
    fun sessionEnded(context: Context, finished: Mode, next: Mode) {
        if (!canPost(context)) return
        val title = when (finished) {
            Mode.FOCUS -> "Focus session done"
            Mode.SHORT -> "Break is over"
            Mode.LONG -> "Long break is over"
        }
        val n = NotificationCompat.Builder(context, CH_END)
            .setSmallIcon(R.drawable.ic_stat_manbo)
            .setContentTitle(title)
            .setContentText("Next up: ${next.label.lowercase()}.")
            .setCategory(Notification.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openApp(context))
            .addAction(0, "Start ${next.label.lowercase()}", toggleAction(context))
            .build()
        NotificationManagerCompat.from(context).notify(ID_END, n)
    }

    fun clearSessionEnded(context: Context) = NotificationManagerCompat.from(context).cancel(ID_END)
}

object SessionEnd {
    fun onFinished(context: Context, finished: Mode, next: Mode) {
        // On screen, the UI pops the button and chimes; otherwise notify (with the chime as its sound)
        if (!AppVisibility.visible) Notifications.sessionEnded(context, finished, next)
    }
}

// -- Do Not Disturb while focusing ---------------------------------------------------

object Dnd {
    fun hasAccess(context: Context) =
        context.getSystemService(NotificationManager::class.java).isNotificationPolicyAccessGranted

    /** Turn DND on while a focus session runs (if enabled and allowed), back off otherwise. */
    fun update(context: Context, s: TimerState) {
        val nm = context.getSystemService(NotificationManager::class.java)
        val prefs = context.getSharedPreferences("dnd", Context.MODE_PRIVATE)
        val active = prefs.getBoolean("active", false)
        val want = SettingsStore.value.dndDuringFocus && s.running && s.mode == Mode.FOCUS
        if (!nm.isNotificationPolicyAccessGranted) return
        if (want && !active) {
            prefs.edit().putBoolean("active", true).putInt("previous", nm.currentInterruptionFilter).apply()
            nm.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_PRIORITY)
        } else if (!want && active) {
            val previous = prefs.getInt("previous", NotificationManager.INTERRUPTION_FILTER_ALL)
            // only undo our own change: if the user changed DND meanwhile, leave it
            if (nm.currentInterruptionFilter == NotificationManager.INTERRUPTION_FILTER_PRIORITY) {
                nm.setInterruptionFilter(previous)
            }
            prefs.edit().putBoolean("active", false).apply()
        }
    }
}

// -- sounds -------------------------------------------------------------------------

object Sounds {
    private var pool: SoundPool? = null
    private val ids = mutableMapOf<String, Int>()
    private var chime: MediaPlayer? = null
    private var attributes: AudioAttributes? = null

    fun init(context: Context) {
        if (pool != null) return
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)   // follows the media volume
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        attributes = attrs
        val p = SoundPool.Builder().setMaxStreams(4).setAudioAttributes(attrs).build()
        for ((key, name) in mapOf("press" to "button_press_2", "pop" to "button_pop_up_2", "tab" to "change_tab")) {
            val id = rawId(context, name)
            if (id != 0) ids[key] = p.load(context, id, 1)
        }
        pool = p
    }

    fun play(key: String) {
        val id = ids[key] ?: return
        pool?.play(id, 1f, 1f, 1, 0, 1f)
    }

    fun chime(context: Context, settings: Settings) {
        val start = Settings.CHIME_STARTS[settings.chimeLength] ?: return  // "off"
        val res = rawId(context, "chime1")
        if (res == 0) return
        chime?.release()
        val level = (settings.chimeVolume / 100f).let { it * it }   // perceptual, like the desktop
        val attrs = attributes ?: AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build()
        val session = context.getSystemService(android.media.AudioManager::class.java).generateAudioSessionId()
        chime = MediaPlayer.create(context, res, attrs, session)?.apply {
            setVolume(level, level)
            seekTo(start)
            setOnCompletionListener { it.release(); if (chime === it) chime = null }
            start()
        }
    }
}
