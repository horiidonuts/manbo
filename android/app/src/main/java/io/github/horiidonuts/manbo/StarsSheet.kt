package io.github.horiidonuts.manbo

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.TextStyle as DateTextStyle
import java.util.Locale
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import kotlin.math.sin

private val DAY_NAMES = listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
private const val STAR_R_DP = 8.5f
private const val LABEL_BAND_DP = 40f

private data class SkyColors(val top: Color, val bottom: Color, val star: Color)

private fun skyColors(theme: String): SkyColors {
    val pal = palette(theme, Mode.FOCUS)
    return SkyColors(   // night up top, a little of the theme's dusk down at the horizon
        top = mix(pal.text, Color.Black, 0.6f),
        bottom = mix(mix(pal.text, pal.button, 0.35f), Color.Black, 0.3f),
        star = mix(pal.bg, Color.White, 0.55f),
    )
}

/** The logo's four-pointed star: one quarter (top tip -> right tip), turned four times. */
private val QUARTER = listOf(
    floatArrayOf(0f, -1f, 0.1799f, -0.5272f, 0.3536f, -0.3534f),
    floatArrayOf(0.5273f, -0.1797f, 1f, 0f, 1f, 0f),
)

private fun starPath(cx: Float, cy: Float, r: Float) = Path().apply {
    moveTo(cx, cy - r)
    for (q in 0 until 4) {
        val c = cos(q * PI / 2).toFloat()
        val s = sin(q * PI / 2).toFloat()
        for (seg in QUARTER) {
            fun px(i: Int) = cx + (seg[i] * c - seg[i + 1] * s) * r
            fun py(i: Int) = cy + (seg[i] * s + seg[i + 1] * c) * r
            cubicTo(px(0), py(0), px(2), py(2), px(4), py(4))
        }
    }
    close()
}

private data class DrawnStar(val x: Float, val y: Float, val session: Session)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StarsSheet(theme: String, onDismiss: () -> Unit) {
    val sessions by HistoryStore.sessions.collectAsStateWithLifecycle()
    val today = LocalDate.now()
    val days = remember(sessions) { StarMath.byDay(sessions) }
    val thisMonday = StarMath.weekStart(today)
    val first = days.keys.minOrNull()?.let(StarMath::weekStart) ?: thisMonday
    var offset by remember { mutableIntStateOf(0) }
    val monday = thisMonday.minusWeeks(offset.toLong())
    var picked by remember { mutableStateOf<Session?>(null) }

    val weekLabel = when (offset) {
        0 -> "This week"
        1 -> "Last week"
        else -> {
            val sunday = monday.plusDays(6)
            fun d(x: LocalDate) = "${x.month.getDisplayName(DateTextStyle.SHORT, Locale.ENGLISH)} ${x.dayOfMonth}"
            "${d(monday)} – ${d(sunday)}"
        }
    }
    val s = StarMath.summary(days, sessions.size, today)

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Your stars", style = TextStyle(fontFamily = MontserratBold, fontSize = 22.sp),
                modifier = Modifier.padding(start = 4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = { offset++; picked = null }, enabled = monday > first) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Previous week")
                }
                Text(weekLabel, style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp),
                    textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
                IconButton(onClick = { offset--; picked = null }, enabled = offset > 0) {
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Next week")
                }
            }
            Sky(monday, days, theme, today, onPick = { picked = it })
            Text(
                picked?.let {
                    val t = Instant.ofEpochMilli(it.end).atZone(ZoneId.systemDefault())
                    "%s %02d:%02d · %s".format(DAY_NAMES[t.dayOfWeek.value - 1], t.hour, t.minute,
                        StarMath.formatMinutes(it.minutes))
                } ?: "Tap a star to see when you earned it",
                style = TextStyle(fontSize = 13.sp), color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Stat(if (s.todayStars == 1) "1 star" else "${s.todayStars} stars",
                    if (s.todayStars > 0) "today · ${StarMath.formatMinutes(s.todayMinutes)}" else "today",
                    Modifier.weight(1f))
                Stat("${s.streak}", if (s.streak == 1) "day in a row" else "days in a row", Modifier.weight(1f))
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Stat(StarMath.formatMinutes(StarMath.weekMinutes(days, monday)),
                    if (offset < 2) "focused ${weekLabel.lowercase()}" else "focused that week", Modifier.weight(1f))
                Stat("${s.totalStars}", if (s.totalStars == 1) "star in all" else "stars in all", Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun Stat(value: String, caption: String, modifier: Modifier) {
    Surface(modifier, shape = RoundedCornerShape(16.dp), color = MaterialTheme.colorScheme.surfaceContainerHigh) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            Text(value, style = TextStyle(fontFamily = MontserratBold, fontSize = 20.sp))
            Text(caption, style = TextStyle(fontSize = 12.sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun Sky(
    monday: LocalDate, days: Map<LocalDate, List<Session>>, theme: String, today: LocalDate,
    onPick: (Session?) -> Unit,
) {
    val colors = skyColors(theme)
    val measurer = rememberTextMeasurer()
    val drawn = remember { ArrayList<DrawnStar>() }
    val emptyText = if (monday == StarMath.weekStart(today)) "Finish a focus session to light your first star"
        else "No stars this week"
    Canvas(
        Modifier
            .fillMaxWidth()
            .height(300.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(Brush.verticalGradient(listOf(colors.top, colors.bottom)))
            .pointerInput(drawn) {
                detectTapGestures { at ->
                    val best = drawn.minByOrNull { hypot(it.x - at.x, it.y - at.y) }
                    onPick(best?.takeIf { hypot(it.x - at.x, it.y - at.y) < 28.dp.toPx() }?.session)
                }
            },
    ) {
        drawn.clear()
        val w = size.width
        val h = size.height
        val colW = w / 7
        val skyH = h - LABEL_BAND_DP.dp.toPx()
        val starR = min(STAR_R_DP.dp.toPx(), colW * 0.1f)   // a narrow sky gets smaller stars

        // faint stardust, the same every time this week is shown
        val dust = StarMath.Mulberry32(monday.toEpochDay().toInt())
        repeat((w * h / (1400 * density * density)).toInt()) {
            val x = dust.next().toFloat() * w
            val y = dust.next().toFloat() * h
            val r = (0.5f + dust.next().toFloat() * 0.8f) * density
            drawCircle(colors.star.copy(alpha = 0.15f + dust.next().toFloat() * 0.3f), r, Offset(x, y))
        }

        var any = false
        for (i in 0 until 7) {
            val day = monday.plusDays(i.toLong())
            val list = days[day].orEmpty()
            val x0 = i * colW
            if (day == today) {
                drawRect(Brush.verticalGradient(listOf(colors.star.copy(alpha = 0f), colors.star.copy(alpha = 0.10f))),
                    topLeft = Offset(x0 + 4.dp.toPx(), 0f), size = androidx.compose.ui.geometry.Size(colW - 8.dp.toPx(), h))
            }
            val alpha = when {
                day == today -> 0.95f
                day > today -> 0.35f
                else -> 0.6f
            }
            val style = TextStyle(color = colors.star.copy(alpha = alpha), fontSize = 11.sp,
                fontWeight = if (day == today) FontWeight.Bold else FontWeight.Normal)
            label(measurer, DAY_NAMES[i], x0 + colW / 2, skyH + 8.dp.toPx(), style)
            label(measurer, "${day.dayOfMonth}", x0 + colW / 2, skyH + 22.dp.toPx(), style)

            if (list.isEmpty()) continue
            any = true
            val pts = StarMath.layoutDay(day, list.size).map { (px, py) ->
                Offset(x0 + px.toFloat() * colW, 6.dp.toPx() + py.toFloat() * (skyH - 12.dp.toPx()))
            }
            // the constellation's lines, in the order the stars were earned
            for (j in 1 until pts.size) {
                drawLine(colors.star.copy(alpha = 0.32f), pts[j - 1], pts[j], strokeWidth = 1.2f * density)
            }
            for ((p, session) in pts.zip(list)) {
                val r = starR * StarMath.starScale(session.minutes).toFloat()
                drawCircle(Brush.radialGradient(listOf(colors.star.copy(alpha = 0.34f), colors.star.copy(alpha = 0f)),
                    center = p, radius = r * 2.4f), r * 2.4f, p)
                drawPath(starPath(p.x, p.y, r), colors.star)
                drawn += DrawnStar(p.x, p.y, session)
            }
        }
        if (!any) label(measurer, emptyText, w / 2, skyH / 2 - 8.dp.toPx(),
            TextStyle(color = colors.star.copy(alpha = 0.75f), fontSize = 13.sp))
    }
}

private fun DrawScope.label(
    measurer: androidx.compose.ui.text.TextMeasurer, text: String, cx: Float, top: Float, style: TextStyle,
) {
    val layout = measurer.measure(text, style)
    drawText(layout, topLeft = Offset(cx - layout.size.width / 2f, top))
}
