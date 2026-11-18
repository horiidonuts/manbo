package io.github.horiidonuts.manbo

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.LocalDate

/** The star layout must match the desktop's (manbo/history.py): values generated there. */
class StarMathTest {
    private val mulberry1 = doubleArrayOf(0.6270739405881613, 0.002735721180215478, 0.5274470399599522)
    private val layouts = listOf(
        Triple(LocalDate.of(2026, 11, 19), 6, doubleArrayOf(0.5459579230099917, 0.3855920253321528, 0.4552342061658118, 0.5916518008921868, 0.6985294691383869, 0.7297778045710652, 0.3936568630755441, 0.8164958723546328, 0.6667810759297206, 0.8928324796744094, 0.30473310881855575, 0.8733869522642925)),
        Triple(LocalDate.of(2026, 1, 1), 12, doubleArrayOf(0.3633118341863155, 0.5798981823353095, 0.5380646348616402, 0.37899143753304554, 0.4957015616434375, 0.2440832892212137, 0.22250220450620356, 0.35218737313321213, 0.2609205738876048, 0.1408662554975052, 0.6727709089806915, 0.1979645329583905, 0.42153014962499086, 0.09278069223218342, 0.3091235776317899, 0.21423918439144274, 0.6570089219785642, 0.31784551192493204, 0.717786172081135, 0.5284077676491463, 0.5965105533444238, 0.6975931096382028, 0.44144739136890676, 0.8103114353909578)),
        Triple(LocalDate.of(2027, 2, 28), 3, doubleArrayOf(0.6134931570105255, 0.09566789901349694, 0.49062597382659134, 0.22625120613598051, 0.22705715504776647, 0.3047686616630664)),
        Triple(LocalDate.of(2026, 11, 17), 9, doubleArrayOf(0.7105686841346324, 0.14451171142980457, 0.43976148737129445, 0.21078105194768684, 0.7552483260875051, 0.24954268526584145, 0.3627186827330991, 0.36303136991744317, 0.306028344433553, 0.48636637220038886, 0.33468727871261916, 0.6529296834449487, 0.7368682597542666, 0.7036433683901633, 0.6015100056898534, 0.578879268361273, 0.6157052805208066, 0.42690295871574246)),
    )

    @Test fun mulberry32MatchesDesktop() {
        val r = StarMath.Mulberry32(1)
        for (x in mulberry1) assertEquals(x, r.next(), 1e-15)
    }

    @Test fun layoutMatchesDesktop() {
        for ((day, n, flat) in layouts) {
            val pts = StarMath.layoutDay(day, n)
            assertEquals(n, pts.size)
            for ((i, p) in pts.withIndex()) {
                assertEquals("$day star $i x", flat[2 * i], p.first, 1e-9)
                assertEquals("$day star $i y", flat[2 * i + 1], p.second, 1e-9)
            }
        }
    }

    @Test fun earlierStarsStayPutAsTheDayGrows() {
        val day = LocalDate.of(2026, 11, 19)
        assertEquals(StarMath.layoutDay(day, 3), StarMath.layoutDay(day, 7).take(3))
    }

    @Test fun streakCountsBackFromTodayOrYesterday() {
        val d = LocalDate.of(2026, 11, 19)
        val days = listOf(d.minusDays(1), d.minusDays(2), d.minusDays(4)).associateWith { listOf(Session(0, 25)) }
        assertEquals(2, StarMath.streak(days, d))
        assertEquals(0, StarMath.streak(days, d.plusDays(1)))
        assertEquals(3, StarMath.streak(days + (d to listOf(Session(1, 25))), d))
    }

    @Test fun formatsMinutes() {
        assertEquals("25 min", StarMath.formatMinutes(25))
        assertEquals("1 h", StarMath.formatMinutes(60))
        assertEquals("2 h 5 min", StarMath.formatMinutes(125))
    }
}
