package io.github.horiidonuts.manbo

import android.content.Context
import android.util.Log
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Focus history: every finished focus session is a star. Same format as the desktop's
 * history.json; synced with the PC by merging on the session's end time.
 */
object HistoryStore {
    private lateinit var file: File
    private val byEnd = sortedMapOf<Long, Int>()
    private val _sessions = MutableStateFlow<List<Session>>(emptyList())
    val sessions: StateFlow<List<Session>> = _sessions

    /** Sessions this phone just recorded: sync sends them to the PC. */
    private val _added = MutableSharedFlow<List<Session>>(extraBufferCapacity = 16)
    val added: SharedFlow<List<Session>> = _added

    @Synchronized
    fun init(context: Context) {
        if (::file.isInitialized) return
        file = File(context.applicationContext.filesDir, "history.json")
        runCatching {
            val arr = JSONObject(file.readText()).getJSONArray("sessions")
            for (i in 0 until arr.length()) {
                val s = arr.getJSONArray(i)
                byEnd[s.getLong(0)] = s.getInt(1)
            }
        }
        publish()
    }

    /** A focus session ended here. */
    @Synchronized
    fun record(end: Long, minutes: Int) {
        if (byEnd.containsKey(end)) return
        byEnd[end] = minutes
        save()
        publish()
        _added.tryEmit(listOf(Session(end, minutes)))
    }

    /** Sessions from the PC; the ones we already have (same end) are skipped. */
    @Synchronized
    fun merge(arr: JSONArray) {
        var changed = false
        for (i in 0 until arr.length()) {
            val s = arr.optJSONArray(i) ?: continue
            val end = s.optLong(0)
            val minutes = s.optInt(1)
            if (end > 0 && minutes in 1..24 * 60 && !byEnd.containsKey(end)) {
                byEnd[end] = minutes
                changed = true
            }
        }
        if (changed) {
            save()
            publish()
        }
    }

    fun toJson(list: List<Session>) = JSONArray().apply {
        for (s in list) put(JSONArray().put(s.end).put(s.minutes))
    }

    private fun publish() {
        _sessions.value = byEnd.map { (end, m) -> Session(end, m) }
    }

    private fun save() {
        try {
            val tmp = File(file.path + ".tmp")
            val all = byEnd.map { (end, m) -> Session(end, m) }
            tmp.writeText(JSONObject().put("version", 1).put("sessions", toJson(all)).toString())
            tmp.renameTo(file)
        } catch (e: Exception) {
            Log.w("Manbo", "can't save the history: $e")
        }
    }
}
