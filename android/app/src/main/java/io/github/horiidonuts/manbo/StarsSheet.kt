package io.github.horiidonuts.manbo

import androidx.compose.foundation.Canvas
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.foundation.layout.statusBars
import androidx.compose.ui.draw.drawBehind
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.scale
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
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import kotlin.math.sin

private val DAY_NAMES get() = if (Lang.turkish) listOf("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")
    else listOf("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
private const val STAR_R_DP = 8.5f
private const val LABEL_BAND_DP = 40f

private const val FADE_DP = 150f   // between the week row and the stars: the horizon glow fades out here
// The whole sheet is one twilight sky, painted behind everything (like the desktop's stars dialog,
// see manbo/stars.py): a light yellow glow and a thin band of pink at the horizon with a few wisps
// of cloud, a long fade through mauve and lavender, periwinkle and royal blue behind the stars,
// indigo and navy behind the stats, and all but black violet at the very bottom.
private val HORIZON_STOPS = listOf(   // dp from the top
    0f to Color(0xFFFFF1CF), 22f to Color(0xFFFFE5DD), 44f to Color(0xFFFCD1D2), 66f to Color(0xFFF1C4CF),
    96f to Color(0xFFDFB3CA), 130f to Color(0xFFC7A1C8), 170f to Color(0xFFB495CA), 215f to Color(0xFFA18BCB),
    270f to Color(0xFF817ACC),
)
private val NIGHT_STOPS = listOf(   // fractions of the height
    0.45f to Color(0xFF686AC8), 0.53f to Color(0xFF4C54C2), 0.60f to Color(0xFF3741B1), 0.67f to Color(0xFF2A339C),
    0.75f to Color(0xFF1A1F7D), 0.83f to Color(0xFF0D0F5D), 0.91f to Color(0xFF070941), 1f to Color(0xFF0D0817),
)
private val CLOUD = Color(0xFFFFF5ED)

/** The whole twilight: gradient, wisps of cloud at the horizon, stardust where it's dark. */
private fun DrawScope.paintSky(star: Color) {
    val w = size.width
    val h = size.height
    val dp = density
    var last = -1f
    val stops = (HORIZON_STOPS.map { (y, c) -> y * dp / h to c } + NIGHT_STOPS).map { (at, c) ->
        last = minOf(1f, maxOf(at, last + 0.002f))
        last to c
    }
    drawRect(Brush.verticalGradient(*stops.toTypedArray(), startY = 0f, endY = h))

    val rnd = StarMath.Mulberry32(7)
    fun r() = rnd.next().toFloat()
    repeat(4 + (w / dp / 90).toInt()) {   // long, flat, soft-edged puffs, thinning out downwards
        val cx = r() * w
        val cy = (8 + Math.pow(rnd.next(), 1.6).toFloat() * 170) * dp
        val fade = maxOf(0f, 1 - cy / (210 * dp))
        repeat(3 + (r() * 3).toInt()) {
            val x = cx + (r() - 0.5f) * 160 * dp
            val y = cy + (r() - 0.5f) * 14 * dp
            val rx = (50 + r() * 90) * dp
            val ry = rx * (0.10f + r() * 0.08f)
            val alpha = (0.16f + r() * 0.22f) * fade
            scale(1f, ry / rx, pivot = Offset(x, y)) {
                drawCircle(Brush.radialGradient(listOf(CLOUD.copy(alpha = alpha), CLOUD.copy(alpha = 0f)),
                    center = Offset(x, y), radius = rx), rx, Offset(x, y))
            }
        }
    }
    repeat((w * h / (1500 * dp * dp)).toInt()) {   // stardust, more of it the darker the sky
        val x = r() * w
        val y = r() * h
        val size = (0.5f + r() * 0.8f) * dp
        val alpha = (0.15f + r() * 0.35f) * ((y / h - 0.3f) / 0.35f).coerceIn(0f, 1f)
        if (alpha > 0.01f) drawCircle(star.copy(alpha = alpha), size, Offset(x, y))
    }
}

private data class SkyColors(val star: Color)

/** The sky itself is the same twilight for every theme; its stars are the theme's. */
private fun skyColors(theme: String) = SkyColors(star = mix(palette(theme, Mode.FOCUS).bg, Color.White, 0.55f))

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
        0 -> t("This week", "Bu hafta")
        1 -> t("Last week", "Geçen hafta")
        else -> {
            val sunday = monday.plusDays(6)
            fun d(x: LocalDate): String {
                val month = x.month.getDisplayName(DateTextStyle.SHORT, Lang.locale)
                return t("$month ${x.dayOfMonth}", "${x.dayOfMonth} $month")
            }
            "${d(monday)} – ${d(sunday)}"
        }
    }
    val s = StarMath.summary(days, sessions.size, today)

    val colors = skyColors(theme)
    // room under the stats: scrolled all the way down, they sit in the middle of the open sheet
    // (which reaches from under the status bar and drag handle down to the bottom of the screen)
    val density = LocalDensity.current
    val windowHeight = LocalView.current.rootView.height
    val statusBar = WindowInsets.statusBars.getTop(density)
    var statsHeight by remember { mutableIntStateOf(0) }
    val tail = with(density) {
        val visible = windowHeight - statusBar - 48.dp.toPx()
        maxOf(40.dp.toPx(), (visible - statsHeight) / 2).toDp()
    }
    // the sky runs edge to edge and down to the very bottom, under the navigation bar too
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = HORIZON_STOPS[0].second,
        contentColor = Color(0xFF2A2140), contentWindowInsets = { WindowInsets(0) }) {
        // the twilight behind everything: title, week, stars and stats all sit on one sky
        Column(Modifier.verticalScroll(rememberScrollState()).drawBehind { paintSky(colors.star) }) {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(t("Your stars", "Yıldızların"), style = TextStyle(fontFamily = MontserratBold, fontSize = 22.sp),
                    modifier = Modifier.padding(start = 4.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = { offset++; picked = null }, enabled = monday > first) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = t("Previous week", "Önceki hafta"))
                    }
                    Text(weekLabel, style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp),
                        textAlign = TextAlign.Center, modifier = Modifier.weight(1f))
                    IconButton(onClick = { offset--; picked = null }, enabled = offset > 0) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = t("Next week", "Sonraki hafta"))
                    }
                }
            }
            Column(Modifier.fillMaxWidth()) {
                Spacer(Modifier.height(FADE_DP.dp))
                Sky(monday, days, colors, today, onPick = { picked = it })
                Column(Modifier.padding(horizontal = 20.dp).onSizeChanged { statsHeight = it.height },
                    verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(
                        picked?.let {
                            val t = Instant.ofEpochMilli(it.end).atZone(ZoneId.systemDefault())
                            "%s %02d:%02d · %s".format(DAY_NAMES[t.dayOfWeek.value - 1], t.hour, t.minute,
                                StarMath.formatMinutes(it.minutes))
                        } ?: t("Tap a star to see when it lit up ✨", "Ne zaman yandığını görmek için bir yıldıza dokun ✨"),
                        style = TextStyle(fontSize = 13.sp), color = colors.star.copy(alpha = 0.7f),
                        textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth(),
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Stat(t(if (s.todayStars == 1) "1 star" else "${s.todayStars} stars", "${s.todayStars} yıldız"),
                            t("today", "bugün") + if (s.todayStars > 0) " · ${StarMath.formatMinutes(s.todayMinutes)}" else "",
                            colors, Modifier.weight(1f))
                        Stat("${s.streak}", t(if (s.streak == 1) "day in a row" else "days in a row", "gün üst üste"),
                            colors, Modifier.weight(1f))
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Stat(StarMath.formatMinutes(StarMath.weekMinutes(days, monday)),
                            when (offset) {
                                0 -> t("focused this week", "bu hafta odak")
                                1 -> t("focused last week", "geçen hafta odak")
                                else -> t("focused that week", "o hafta odak")
                            },
                            colors, Modifier.weight(1f))
                        Stat("${s.totalStars}", t(if (s.totalStars == 1) "star in all" else "stars in all", "toplam yıldız"),
                            colors, Modifier.weight(1f))
                    }
                }
                Spacer(Modifier.height(tail))
            }
        }
    }
}

@Composable
private fun Stat(value: String, caption: String, colors: SkyColors, modifier: Modifier) {
    // a pane of frosted glass on the night sky
    Surface(modifier, shape = RoundedCornerShape(16.dp), color = colors.star.copy(alpha = 0.09f)) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
            Text(value, style = TextStyle(fontFamily = MontserratBold, fontSize = 20.sp), color = colors.star)
            Text(caption, style = TextStyle(fontSize = 12.sp), color = colors.star.copy(alpha = 0.65f))
        }
    }
}

@Composable
private fun Sky(
    monday: LocalDate, days: Map<LocalDate, List<Session>>, colors: SkyColors, today: LocalDate,
    onPick: (Session?) -> Unit,
) {
    val measurer = rememberTextMeasurer()
    val drawn = remember { ArrayList<DrawnStar>() }
    val emptyText = if (monday == StarMath.weekStart(today))
        t("The sky's a little empty… shall we light the first star? 🌙", "Gökyüzü biraz boş… ilk yıldızı yakalım mı? 🌙")
        else t("A quiet week in the sky 🌙", "Gökyüzü bu hafta sessizdi 🌙")
    Canvas(
        Modifier
            .fillMaxWidth()
            .height(300.dp)
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

        // (the twilight itself, stardust included, is paintSky behind the whole sheet)
        var any = false
        for (i in 0 until 7) {
            val day = monday.plusDays(i.toLong())
            val list = days[day].orEmpty()
            val x0 = i * colW
            if (day == today) {   // brightest at its name, fading out at both ends
                drawRect(Brush.verticalGradient(0f to colors.star.copy(alpha = 0f), 0.8f to colors.star.copy(alpha = 0.10f),
                    1f to colors.star.copy(alpha = 0f)),
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
        if (!any) label(measurer, emptyText, w / 2, skyH / 2 - 16.dp.toPx(),
            TextStyle(color = colors.star.copy(alpha = 0.75f), fontSize = 13.sp, textAlign = TextAlign.Center),
            maxWidth = (w - 64.dp.toPx()).toInt())
    }
}

private fun DrawScope.label(
    measurer: androidx.compose.ui.text.TextMeasurer, text: String, cx: Float, top: Float, style: TextStyle,
    maxWidth: Int = Int.MAX_VALUE,   // wraps onto more lines past this
) {
    val layout = measurer.measure(text, style,
        constraints = androidx.compose.ui.unit.Constraints(maxWidth = maxWidth.coerceAtLeast(1)))
    drawText(layout, topLeft = Offset(cx - layout.size.width / 2f, top))
}
