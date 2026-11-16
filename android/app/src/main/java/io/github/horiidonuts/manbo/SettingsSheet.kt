package io.github.horiidonuts.manbo

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsSheet(settings: Settings, ink: Color, openDndAccess: () -> Unit, onDismiss: () -> Unit) {
    val context = LocalContext.current
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 24.dp).padding(bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Heading("Timer")
            Stepper("Focus", "minutes", settings.focusMinutes, Settings.RANGES.getValue("focusMinutes")) { v ->
                SettingsStore.update { it.copy(focusMinutes = v) }
            }
            Stepper("Short break", "minutes", settings.shortBreakMinutes, Settings.RANGES.getValue("shortBreakMinutes")) { v ->
                SettingsStore.update { it.copy(shortBreakMinutes = v) }
            }
            Stepper("Long break", "minutes", settings.longBreakMinutes, Settings.RANGES.getValue("longBreakMinutes")) { v ->
                SettingsStore.update { it.copy(longBreakMinutes = v) }
            }
            Stepper("Long break interval", "focus sessions", settings.longBreakInterval, Settings.RANGES.getValue("longBreakInterval")) { v ->
                SettingsStore.update { it.copy(longBreakInterval = v) }
            }

            Heading("Focus")
            Toggle("Do Not Disturb while focusing", "Silence other notifications while a focus session runs",
                settings.dndDuringFocus) { on ->
                if (on && !Dnd.hasAccess(context)) openDndAccess()   // Android asks once for DND access
                SettingsStore.update { it.copy(dndDuringFocus = on) }
            }

            Heading("Appearance")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (t in THEMES) {
                    FilterChip(selected = settings.theme == t.key, onClick = { SettingsStore.update { it.copy(theme = t.key) } },
                        label = { Text(t.name) })
                }
            }
            Toggle("Rolling digits", "Digits roll as time passes and when the timer resets", settings.rollingDigits) { on ->
                SettingsStore.update { it.copy(rollingDigits = on) }
            }

            Heading("Sound")
            Toggle("Button sounds", "Clicks for the button and when switching modes", settings.buttonSounds) { on ->
                SettingsStore.update { it.copy(buttonSounds = on) }
            }
            Text("Chime", style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (len in Settings.CHIME_LENGTHS) {
                    FilterChip(selected = settings.chimeLength == len, onClick = {
                        SettingsStore.update { it.copy(chimeLength = len) }
                        Sounds.chime(context, SettingsStore.value)
                    }, label = { Text(len.replaceFirstChar { it.uppercase() }) })
                }
            }
            Text("Chime volume · ${settings.chimeVolume}%", style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Slider(
                value = settings.chimeVolume.toFloat(), valueRange = 0f..100f,
                enabled = settings.chimeLength != "off",
                onValueChange = { v -> SettingsStore.update { it.copy(chimeVolume = v.toInt()) } },
                onValueChangeFinished = { Sounds.chime(context, SettingsStore.value) },
            )
        }
    }
}

@Composable
private fun Heading(text: String) {
    Spacer(Modifier.height(10.dp))
    Text(text, style = TextStyle(fontFamily = MontserratBold, fontSize = 15.sp))
}

@Composable
private fun Toggle(title: String, subtitle: String, value: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text(title, style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Text(subtitle, style = TextStyle(fontFamily = MontserratMedium, fontSize = 12.sp), color = Color.Gray)
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked = value, onCheckedChange = onChange)
    }
}

@Composable
private fun Stepper(title: String, unit: String, value: Int, range: IntRange, onChange: (Int) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text(title, style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Text(unit, style = TextStyle(fontFamily = MontserratMedium, fontSize = 12.sp), color = Color.Gray)
        }
        FilledTonalIconButton(onClick = { if (value > range.first) onChange(value - 1) }) { Text("−", fontSize = 20.sp) }
        Text("$value", style = TextStyle(fontFamily = MontserratBold, fontSize = 18.sp), modifier = Modifier.width(44.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        FilledTonalIconButton(onClick = { if (value < range.last) onChange(value + 1) }) { Text("+", fontSize = 20.sp) }
    }
}
