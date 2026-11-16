package io.github.horiidonuts.manbo

import androidx.compose.ui.graphics.Color

/** Same palettes as the desktop app (manbo/themes.py). */
data class Palette(val bg: Color, val button: Color, val text: Color)

data class Theme(val key: String, val name: String, val modes: Map<Mode, Palette>)

private fun c(hex: String) = Color(android.graphics.Color.parseColor(hex))

val THEMES = listOf(
    Theme("blossom", "Blossom", mapOf(
        Mode.FOCUS to Palette(c("#FFE5D9"), c("#F4ACB7"), c("#7E6770")),
        Mode.SHORT to Palette(c("#D8E2DC"), c("#F4ACB7"), c("#7E6770")),
        Mode.LONG to Palette(c("#FFCAD4"), c("#9D8189"), c("#7E6770")),
    )),
    Theme("cotton", "Cotton Candy", mapOf(
        Mode.FOCUS to Palette(c("#FFC8DD"), c("#CDB4DB"), c("#5E4B70")),
        Mode.SHORT to Palette(c("#BDE0FE"), c("#FFAFCC"), c("#5E4B70")),
        Mode.LONG to Palette(c("#CDB4DB"), c("#A2D2FF"), c("#5E4B70")),
    )),
    Theme("coastal", "Coastal", mapOf(
        Mode.FOCUS to Palette(c("#F8F4F1"), c("#CEAAA1"), c("#3B7DA1")),
        Mode.SHORT to Palette(c("#EAF0F2"), c("#98B9CB"), c("#3B7DA1")),
        Mode.LONG to Palette(c("#F1EEE4"), c("#3B7DA1"), c("#3B7DA1")),
    )),
)

fun palette(theme: String, mode: Mode): Palette =
    (THEMES.firstOrNull { it.key == theme } ?: THEMES[0]).modes.getValue(mode)

fun mix(a: Color, b: Color, t: Float) = Color(
    red = a.red + (b.red - a.red) * t,
    green = a.green + (b.green - a.green) * t,
    blue = a.blue + (b.blue - a.blue) * t,
    alpha = 1f,
)

fun luminance(c: Color): Float {
    fun lin(v: Float) = if (v <= 0.03928f) v / 12.92f else Math.pow(((v + 0.055f) / 1.055f).toDouble(), 2.4).toFloat()
    return 0.2126f * lin(c.red) + 0.7152f * lin(c.green) + 0.0722f * lin(c.blue)
}
