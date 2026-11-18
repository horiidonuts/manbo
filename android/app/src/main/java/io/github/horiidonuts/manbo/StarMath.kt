package io.github.horiidonuts.manbo

import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.sin
import kotlin.math.sqrt

/** A finished focus session: [end] is the wall-clock ms it ended at (its id on every device). */
data class Session(val end: Long, val minutes: Int)

/**
 * Stats and the star layout. Mirrors manbo/history.py so a day's constellation looks
 * the same on the phone and the PC: keep the two in step.
 */
object StarMath {
    // -- stats -----------------------------------------------------------------------

    fun localDay(end: Long, zone: ZoneId = ZoneId.systemDefault()): LocalDate =
        Instant.ofEpochMilli(end).atZone(zone).toLocalDate()

    fun weekStart(day: LocalDate): LocalDate = day.minusDays((day.dayOfWeek.value - 1).toLong())   // Monday

    fun byDay(sessions: List<Session>, zone: ZoneId = ZoneId.systemDefault()): Map<LocalDate, List<Session>> =
        sessions.sortedBy { it.end }.groupBy { localDay(it.end, zone) }

    /** Days in a row with at least one star, up to today (or yesterday: today isn't over). */
    fun streak(days: Map<LocalDate, List<Session>>, today: LocalDate): Int {
        var day = if (days.containsKey(today)) today else today.minusDays(1)
        var n = 0
        while (days.containsKey(day)) {
            n++
            day = day.minusDays(1)
        }
        return n
    }

    data class Summary(val todayStars: Int, val todayMinutes: Int, val streak: Int, val totalStars: Int)

    fun summary(days: Map<LocalDate, List<Session>>, total: Int, today: LocalDate): Summary {
        val todays = days[today].orEmpty()
        return Summary(todays.size, todays.sumOf { it.minutes }, streak(days, today), total)
    }

    fun weekMinutes(days: Map<LocalDate, List<Session>>, monday: LocalDate) =
        (0L until 7L).sumOf { i -> days[monday.plusDays(i)].orEmpty().sumOf { it.minutes } }

    fun formatMinutes(minutes: Int): String {
        val h = minutes / 60
        val m = minutes % 60
        return when {
            h > 0 && m > 0 -> "$h h $m min"
            h > 0 -> "$h h"
            else -> "$m min"
        }
    }

    // -- star layout -------------------------------------------------------------------
    //
    // Each day is a column of the week's sky. Its stars are a little random walk: the first
    // lands anywhere, every next one a step away from the one before, so a day's sessions join
    // up into a constellation. A PRNG seeded with the date keeps them where they are as the
    // day gets more stars.

    private const val COLUMN_ASPECT = 2.4
    private const val STEP_MIN = 0.30
    private const val STEP_MAX = 0.52
    private const val MIN_GAP = 0.24
    private const val MARGIN_X = 0.22
    private const val MARGIN_Y = 0.07
    private const val TRIES = 24

    /** mulberry32, bit for bit like the desktop's: numbers in [0, 1). */
    class Mulberry32(seed: Int) {
        private var a = seed
        fun next(): Double {
            a += 0x6D2B79F5
            var t = (a xor (a ushr 15)) * (1 or a)
            t = (t + ((t xor (t ushr 7)) * (61 or t))) xor t
            return ((t xor (t ushr 14)).toLong() and 0xFFFFFFFFL).toDouble() / 4294967296.0
        }
    }

    fun daySeed(day: LocalDate) = day.year * 10000 + day.monthValue * 100 + day.dayOfMonth

    /** Positions of a day's [count] stars, as (x, y) fractions of its column. */
    fun layoutDay(day: LocalDate, count: Int): List<Pair<Double, Double>> {
        val rnd = Mulberry32(daySeed(day))
        val loY = MARGIN_Y * COLUMN_ASPECT
        val hiY = (1 - MARGIN_Y) * COLUMN_ASPECT
        val pts = ArrayList<Pair<Double, Double>>()
        fun inside(x: Double, y: Double) = x >= MARGIN_X && x <= 1 - MARGIN_X && y >= loY && y <= hiY
        fun gap(x: Double, y: Double) = pts.minOfOrNull { (px, py) -> hypot(x - px, y - py) } ?: 9.0

        for (i in 0 until count) {
            var best: Pair<Double, Double>? = null
            var bestGap = -1.0
            for (t in 0 until TRIES) {
                val x: Double
                val y: Double
                if (i == 0) {
                    x = MARGIN_X + rnd.next() * (1 - 2 * MARGIN_X)
                    y = loY + rnd.next() * (hiY - loY)
                } else {
                    val angle = rnd.next() * 2 * PI
                    val step = STEP_MIN + rnd.next() * (STEP_MAX - STEP_MIN)
                    x = pts.last().first + cos(angle) * step
                    y = pts.last().second + sin(angle) * step
                    if (!inside(x, y)) continue
                }
                val g = gap(x, y)
                if (g > bestGap) {
                    best = x to y
                    bestGap = g
                }
                if (g >= MIN_GAP) break
            }
            pts += best ?: ((MARGIN_X + rnd.next() * (1 - 2 * MARGIN_X)) to (loY + rnd.next() * (hiY - loY)))
        }
        return pts.map { (x, y) -> x to y / COLUMN_ASPECT }
    }

    /** Longer sessions make bigger stars (a 25-minute one is 1). */
    fun starScale(minutes: Int) = sqrt(minutes / 25.0).coerceIn(0.7, 1.6)
}
