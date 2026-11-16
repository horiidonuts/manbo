package io.github.horiidonuts.manbo

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.Easing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin
import kotlin.math.sqrt

// Same tuning as the desktop button (manbo/pushbutton.py)
private const val VIEW_ANGLE = 27.0
private const val BUTTON_WIDTH = 0.8f
private const val BUTTON_HEIGHT = 0.66f
private const val BUTTON_HEIGHT_DOWN = 0.09f
private const val HOUSING_HEIGHT = 0.15f
private const val HOUSING_R = 1.22f
private const val HOLE_R = 1.045f
private val SQUASH = sin(VIEW_ANGLE * PI / 180).toFloat()
private val HEIGHT_SCALE = cos(VIEW_ANGLE * PI / 180).toFloat()
private const val POP_BOUNCE = 0.12f

private val EaseOutBack = CubicBezierEasing(0.34f, 1.56f, 0.64f, 1f)

/** Ease-out-bounce with an adjustable rebound (see bounce_out in pushbutton.py). */
private fun bounceOut(t: Float, height: Float): Float {
    val e = sqrt(height.coerceIn(0f, 0.9f))
    val segments = mutableListOf(1f)
    var k = e
    while (k * k > 0.005f && segments.size < 6) {
        segments.add(2 * k); k *= e
    }
    var x = t * segments.sum()
    if (x < 1f) return x * x
    x -= 1f
    var peak = e
    for (d in segments.drop(1)) {
        if (x < d) {
            val u = x - d / 2
            return 1 - (peak * peak - u * u)
        }
        x -= d
        peak *= e
    }
    return 1f
}

private data class Geom(val cx: Float, val cb: Float, val r: Float)

private fun layout(w: Float, h: Float): Geom {
    val above = BUTTON_HEIGHT * HEIGHT_SCALE + BUTTON_WIDTH * SQUASH
    val below = BUTTON_WIDTH * HOUSING_R * SQUASH + HOUSING_HEIGHT * HEIGHT_SCALE + 0.04f
    val r = min(w * 0.34f, h * 0.92f / (above + below))
    return Geom(w / 2, h / 2 + r * (above - below) / 2, r)
}

private fun hit(g: Geom, p: Offset): Boolean {
    val rb = g.r * BUTTON_WIDTH
    val big = rb * HOUSING_R
    val ytop = g.cb - g.r * BUTTON_HEIGHT * HEIGHT_SCALE
    fun inEl(ex: Float, ey: Float, rx: Float, ry: Float) =
        ((p.x - ex) / rx).pow(2) + ((p.y - ey) / ry).pow(2) <= 1
    return inEl(g.cx, g.cb, big, big * SQUASH) || inEl(g.cx, ytop, rb, rb * SQUASH) ||
        (kotlin.math.abs(p.x - g.cx) <= rb && p.y in ytop..g.cb)
}

private fun ellipse(cx: Float, cy: Float, rx: Float, ry: Float) = Rect(cx - rx, cy - ry, cx + rx, cy + ry)

private fun cylinderSide(cx: Float, ytop: Float, ybot: Float, rx: Float, ry: Float) = Path().apply {
    moveTo(cx - rx, ytop)
    lineTo(cx - rx, ybot)
    arcTo(ellipse(cx, ybot, rx, ry), 180f, -180f, false)   // front half of the bottom ellipse
    lineTo(cx + rx, ytop)
    close()
}

@Composable
fun PushButton3D(
    down: Boolean,
    bg: Color,
    face: Color,
    ink: Color,
    onPress: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val p = remember { Animatable(if (down) 1f else 0f) }
    LaunchedEffect(down) {
        if (down) {
            p.animateTo(1f, tween(150, easing = EaseOutBack))
        } else {
            p.animateTo(0f, tween(100, easing = Easing { bounceOut(it, POP_BOUNCE) }))
        }
    }
    Canvas(
        modifier.pointerInput(Unit) {
            detectTapGestures { pos ->
                if (hit(layout(size.width.toFloat(), size.height.toFloat()), pos)) onPress()
            }
        }
    ) {
        drawButton(p.value, down, bg, face, ink)
    }
}

private fun DrawScope.drawButton(p: Float, down: Boolean, bg: Color, face: Color, ink: Color) {
    val g = layout(size.width, size.height)
    val rb = g.r * BUTTON_WIDTH
    val big = rb * HOUSING_R
    val white = Color.White

    // housing: side + top, then the hole
    drawPath(cylinderSide(g.cx, g.cb, g.cb + g.r * HOUSING_HEIGHT * HEIGHT_SCALE, big, big * SQUASH), mix(bg, ink, 0.28f))
    ellipse(g.cx, g.cb, big, big * SQUASH).let { drawOval(mix(bg, white, 0.45f), it.topLeft, it.size) }
    val hr = rb * HOLE_R
    ellipse(g.cx, g.cb, hr, hr * SQUASH).let { drawOval(mix(bg, ink, 0.45f), it.topLeft, it.size) }

    // the button (the back-out overshoot may push p a bit past 1)
    val height = BUTTON_HEIGHT - (BUTTON_HEIGHT - BUTTON_HEIGHT_DOWN) * p
    val ytop = g.cb - g.r * height.coerceAtLeast(0f) * HEIGHT_SCALE
    drawPath(cylinderSide(g.cx, ytop, g.cb, rb, rb * SQUASH), mix(mix(face, Color.Black, 0.22f), ink, 0.18f))
    ellipse(g.cx, ytop, rb, rb * SQUASH).let { drawOval(face, it.topLeft, it.size) }

    // play / pause, laid flat on the top face
    val icon = if (luminance(face) > 0.68f) mix(face, ink, 0.75f) else mix(face, white, 0.9f)
    val s = rb * 0.42f
    withTransform({
        translate(g.cx, ytop)
        scale(1f, SQUASH, pivot = Offset.Zero)
    }) {
        val path = Path()
        if (down) {
            val bw = s * 0.24f; val bh = s * 0.9f; val gap = s * 0.38f
            for (x0 in listOf(-gap / 2 - bw, gap / 2)) {
                path.addRoundRect(androidx.compose.ui.geometry.RoundRect(
                    Rect(Offset(x0, -bh / 2), Size(bw, bh)),
                    androidx.compose.ui.geometry.CornerRadius(bw * 0.4f),
                ))
            }
        } else {
            path.moveTo(-s * 0.32f, -s * 0.5f)
            path.lineTo(-s * 0.32f, s * 0.5f)
            path.lineTo(s * 0.52f, 0f)
            path.close()
        }
        drawPath(path, icon, style = Fill)
        drawPath(path, icon, style = Stroke(width = s * 0.16f, join = StrokeJoin.Round))
    }
}
