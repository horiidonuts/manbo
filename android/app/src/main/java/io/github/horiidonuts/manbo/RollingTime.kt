package io.github.horiidonuts.manbo

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle

private val EaseOutCubic = CubicBezierEasing(0.33f, 1f, 0.68f, 1f)

fun formatTime(secs: Int) = "%02d:%02d".format(secs / 60, secs % 60)

/**
 * MM:SS where each changed character rolls like an odometer: down while
 * counting down, up when the time jumps up (reset, mode switch, next session).
 */
@Composable
fun RollingTime(seconds: Int, style: TextStyle, color: Color, animate: Boolean, modifier: Modifier = Modifier) {
    val text = formatTime(seconds)
    val last = remember { intArrayOf(seconds) }
    val up = seconds > last[0]
    last[0] = seconds
    Row(modifier) {
        text.forEachIndexed { i, ch ->
            // key by position from the right so "99:59" -> "100:00" keeps the seconds slots
            androidx.compose.runtime.key(text.length - i) {
                AnimatedContent(
                    targetState = ch,
                    modifier = Modifier.clipToBounds(),
                    transitionSpec = {
                        if (!animate) {
                            (slideInVertically(tween(0)) { 0 }) togetherWith (slideOutVertically(tween(0)) { 0 })
                        } else if (up) {
                            val spec = tween<androidx.compose.ui.unit.IntOffset>(380, easing = EaseOutCubic)
                            slideInVertically(spec) { it } togetherWith slideOutVertically(spec) { -it }
                        } else {
                            val spec = tween<androidx.compose.ui.unit.IntOffset>(260, easing = EaseOutCubic)
                            slideInVertically(spec) { -it } togetherWith slideOutVertically(spec) { it }
                        }
                    },
                    label = "digit",
                ) { c ->
                    Text(c.toString(), style = style, color = color)
                }
            }
        }
    }
}
