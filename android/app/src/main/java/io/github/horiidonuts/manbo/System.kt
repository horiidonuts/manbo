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
import android.os.Build
import android.media.MediaPlayer
import android.media.SoundPool
import android.net.Uri
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import java.text.DateFormat
import java.util.Date

/** Is the main screen showing? (Then no session-end notification, the screen shows it.) */
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
        TimerEngine.finishIfDue()   // off screen this starts ChimeService (exact alarms may start one)
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
    private const val CH_END = "session_end_quiet"
    private const val CH_SYNC = "sync"
    private const val ID_ONGOING = 1
    const val ID_END = 2
    const val ID_SYNC = 3

    fun createChannels(context: Context) {
        val nm = context.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_TIMER, t("Running timer", "Çalışan zamanlayıcı"), NotificationManager.IMPORTANCE_LOW).apply {
            description = t("The countdown while a session runs", "Seans sürerken geri sayım")
            setShowBadge(false)
        })
        nm.deleteNotificationChannel("session_end")   // 0.3.0's channel, which played the chime itself
        nm.createNotificationChannel(NotificationChannel(CH_END, t("Session finished", "Seans bitti"), NotificationManager.IMPORTANCE_HIGH).apply {
            description = t("When a focus session or break is over (Manbo plays its chime itself)",
                "Odak seansı ya da mola bitince (zili Manbo kendisi çalar)")
            setSound(null, null)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 120, 80, 120)
        })
        nm.createNotificationChannel(NotificationChannel(CH_SYNC, t("PC sync", "Bilgisayarla senkron"), NotificationManager.IMPORTANCE_MIN).apply {
            description = t("Shown while Manbo stays connected to your PC in the background",
                "Manbo arka planda bilgisayarına bağlıyken görünür")
            setShowBadge(false)
        })
    }

    // the permission only exists on Android 13+; before that notifications are allowed by default
    private fun canPost(context: Context) = Build.VERSION.SDK_INT < 33 ||
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
            .setContentText(if (s.mode == Mode.FOCUS) t("Focusing till $endsAt 🌱", "Odak · bitiş $endsAt 🌱")
                else t("Resting till $endsAt ☁️", "Mola · bitiş $endsAt ☁️"))
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
            .addAction(0, t("Pause", "Duraklat"), toggleAction(context))
            .build()
        nm.notify(ID_ONGOING, n)
    }

    /** A session ended while the app wasn't on screen. */
    fun sessionEnded(context: Context, finished: Mode, next: Mode) {
        if (canPost(context)) NotificationManagerCompat.from(context).notify(ID_END, sessionEndNotification(context, finished, next))
    }

    fun sessionEndNotification(context: Context, finished: Mode, next: Mode): Notification {
        val title = when (finished) {
            Mode.FOCUS -> t("Yay, another star! 🌟", "Yaşasın, bir yıldız daha! 🌟")
            Mode.SHORT -> t("Break's over! ✨", "Mola bitti! ✨")
            Mode.LONG -> t("Long break's over! 🌸", "Uzun mola bitti! 🌸")
        }
        val body = when {
            finished != Mode.FOCUS -> t("Ready to shine again?", "Hadi yine parlayalım!")
            next == Mode.LONG -> t("Long break time~ you earned it 🍵", "Uzun mola zamanı~ hak ettin 🍵")
            else -> t("Break time~ stretch a little ☁️", "Mola zamanı~ biraz gerin ☁️")
        }
        val start = when (next) {
            Mode.FOCUS -> t("Start focus", "Odağı başlat")
            Mode.SHORT -> t("Start short break", "Kısa molayı başlat")
            Mode.LONG -> t("Start long break", "Uzun molayı başlat")
        }
        val n = NotificationCompat.Builder(context, CH_END)
            .setSmallIcon(R.drawable.ic_stat_manbo)
            .setContentTitle(title)
            .setContentText(body)
            .setCategory(Notification.CATEGORY_ALARM)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(openApp(context))
            .addAction(0, start, toggleAction(context))
            .build()
        return n
    }

    fun syncNotification(context: Context, st: SyncLink.Status): Notification {
        val text = when (st.state) {
            SyncLink.State.CONNECTED -> t("In sync with ${st.pc} 💞", "${st.pc} ile senkron 💞")
            SyncLink.State.NO_PERMISSION -> t("Allow \"Nearby devices\" so I can find your PC 🙏",
                "Bilgisayarını bulabilmem için \"Yakındaki cihazlar\" iznini ver 🙏")
            else -> t("Looking for ${st.pc.ifEmpty { "your PC" }} 🔍", "${st.pc.ifEmpty { "Bilgisayarını" }} arıyorum 🔍")
        }
        return NotificationCompat.Builder(context, CH_SYNC)
            .setSmallIcon(R.drawable.ic_stat_manbo)
            .setContentTitle(text)
            .setOngoing(true)
            .setSilent(true)
            .setShowWhen(false)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setContentIntent(openApp(context))
            .build()
    }

    fun showSync(context: Context, st: SyncLink.Status) {
        if (canPost(context)) NotificationManagerCompat.from(context).notify(ID_SYNC, syncNotification(context, st))
    }

    fun clearSessionEnded(context: Context) = NotificationManagerCompat.from(context).cancel(ID_END)
}

object SessionEnd {
    fun onFinished(context: Context, finished: Mode, next: Mode) {
        // synced with the PC: it plays the chime, the phone only buzzes (the screen or the notification)
        if (SyncLink.connected) {
            if (!AppVisibility.visible) Notifications.sessionEnded(context, finished, next)
            return
        }
        // The chime plays on the media volume, so it's heard in vibrate mode too.
        if (AppVisibility.visible) return Sounds.chime(context, SettingsStore.value)
        // Off screen Android 17 mutes background audio unless a foreground service plays it on
        // the alarm stream; the session-end notification (which only vibrates) is its notification.
        try {
            ContextCompat.startForegroundService(context, ChimeService.intent(context, finished, next))
        } catch (e: IllegalStateException) {   // not allowed to start one right now
            Notifications.sessionEnded(context, finished, next)
            Sounds.chime(context, SettingsStore.value, alarm = true)
        }
    }
}

/** Plays the session-end chime in the foreground, then leaves its notification behind. */
class ChimeService : android.app.Service() {
    override fun onBind(intent: Intent?) = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        TimerEngine.init(this)
        val finished = Mode.of(intent?.getStringExtra(EXTRA_FINISHED))
        val next = Mode.of(intent?.getStringExtra(EXTRA_NEXT))
        ServiceCompat.startForeground(
            this, Notifications.ID_END, Notifications.sessionEndNotification(this, finished, next),
            android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK,
        )
        Sounds.chime(this, SettingsStore.value, alarm = true)
        Sounds.whenChimeDone {
            stopForeground(STOP_FOREGROUND_DETACH)   // the notification stays
            stopSelf(startId)
        }
        return START_NOT_STICKY
    }

    companion object {
        private const val EXTRA_FINISHED = "finished"
        private const val EXTRA_NEXT = "next"
        fun intent(context: Context, finished: Mode, next: Mode) = Intent(context, ChimeService::class.java)
            .putExtra(EXTRA_FINISHED, finished.key).putExtra(EXTRA_NEXT, next.key)
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

    fun init(context: Context) {
        if (pool != null) return
        val attrs = AudioAttributes.Builder()
            .setUsage(AudioAttributes.USAGE_MEDIA)   // follows the media volume
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
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

    private val waiters = mutableListOf<() -> Unit>()
    private val main = android.os.Handler(android.os.Looper.getMainLooper())

    /** Run [done] once the chime has finished (right away if none is playing; at most ~9 s later). */
    fun whenChimeDone(done: () -> Unit) {
        if (chime == null) return done()
        var called = false
        val once = { if (!called) { called = true; done() } }
        waiters += once
        main.postDelayed(once, 9_000)
    }

    private fun chimeEnded(player: MediaPlayer) {
        player.release()
        if (chime === player) chime = null
        if (chime == null) waiters.toList().also { waiters.clear() }.forEach { it() }
    }

    /**
     * [alarm]: play on the alarm stream. Off screen that's the only audio Android 17 lets an
     * exact-alarm app's background-started service play (and it rings in vibrate mode / DND).
     */
    fun chime(context: Context, settings: Settings, alarm: Boolean = false) {
        val start = Settings.CHIME_STARTS[settings.chimeLength] ?: return  // "off"
        val res = rawId(context, "chime1")
        if (res == 0) return
        chime?.let { chimeEnded(it) }
        val level = (settings.chimeVolume / 100f).let { it * it }   // perceptual, like the desktop
        val attrs = AudioAttributes.Builder()
            .setUsage(if (alarm) AudioAttributes.USAGE_ALARM else AudioAttributes.USAGE_MEDIA)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()
        val session = context.getSystemService(android.media.AudioManager::class.java).generateAudioSessionId()
        chime = MediaPlayer.create(context, res, attrs, session)?.apply {
            setVolume(level, level)
            seekTo(start)
            setOnCompletionListener { chimeEnded(it) }
            start()
        }
    }
}
