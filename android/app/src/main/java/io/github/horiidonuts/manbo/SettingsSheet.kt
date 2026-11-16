package io.github.horiidonuts.manbo

import android.view.HapticFeedbackConstants
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalView
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
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
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.TextButton
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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
fun SettingsSheet(settings: Settings, ink: Color, openDndAccess: () -> Unit, pairWithPc: () -> Unit, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val pairing by SyncStore.pairing.collectAsStateWithLifecycle()
    val link by SyncLink.status.collectAsStateWithLifecycle()
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

            Heading("PC sync")
            val pc = pairing
            if (pc == null) {
                Text("Keep the timer in step with Manbo on your computer: start, pause or skip on either one. " +
                    "On the PC open Preferences → Phone → Show code, then scan it here or with your camera app.",
                    style = TextStyle(fontFamily = MontserratMedium, fontSize = 13.sp), color = Color.Gray)
                FilledTonalButton(onClick = pairWithPc) { Text("Scan code") }
            } else {
                val state = when (link.state) {
                    SyncLink.State.CONNECTED -> "Connected"
                    SyncLink.State.NO_PERMISSION -> "Needs \"Nearby devices\" permission"
                    SyncLink.State.SEARCHING -> "Looking for it… (same Wi-Fi? Manbo open there?)"
                    else -> "Not connected"
                }
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.weight(1f)) {
                        Text(pc.name, style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
                        Text(state, style = TextStyle(fontFamily = MontserratMedium, fontSize = 12.sp), color = Color.Gray)
                    }
                    TextButton(onClick = {
                        SyncStore.unpair()
                        SyncLink.restart()
                        SyncService.update(context)
                    }) { Text("Unpair") }
                }
                if (link.state == SyncLink.State.NO_PERMISSION) {
                    FilledTonalButton(onClick = pairWithPc) { Text("Allow and scan again") }
                }
                Toggle("Stay connected in background",
                    "So a session started on the PC starts here too (with Do Not Disturb). Shows a quiet notification.",
                    settings.syncInBackground) { on ->
                    SettingsStore.update { it.copy(syncInBackground = on) }
                    SyncService.update(context)
                }
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
        // read the latest value inside the repeat loop, not the one from when the press began
        val current by rememberUpdatedState(value)
        val change by rememberUpdatedState(onChange)
        RepeatButton("−", enabled = value > range.first) {
            if (current > range.first) { change(current - 1); true } else false
        }
        Text("$value", style = TextStyle(fontFamily = MontserratBold, fontSize = 18.sp), modifier = Modifier.width(44.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        RepeatButton("+", enabled = value < range.last) {
            if (current < range.last) { change(current + 1); true } else false
        }
    }
}

/**
 * A round − / + button: tap for one step, hold to keep stepping, faster the longer it's held.
 * [step] returns false once the end of the range is reached.
 */
@Composable
private fun RepeatButton(label: String, enabled: Boolean, step: () -> Boolean) {
    val view = LocalView.current
    val scope = rememberCoroutineScope()
    val doStep by rememberUpdatedState(step)
    var pressed by remember { mutableStateOf(false) }
    val base = MaterialTheme.colorScheme.secondaryContainer
    Box(
        Modifier
            .size(40.dp)
            .clip(CircleShape)
            .background(if (pressed) mix(base, Color.Black, 0.08f) else base)
            .pointerInput(Unit) {
                detectTapGestures(onPress = {
                    pressed = true
                    val repeat = scope.launch {
                        if (!doStep()) return@launch
                        view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                        delay(400)                      // a tap is just one step
                        var interval = 110L
                        while (isActive && doStep()) {
                            view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                            delay(interval)
                            interval = maxOf(35L, (interval * 0.9).toLong())   // speed up while held
                        }
                    }
                    tryAwaitRelease()
                    repeat.cancel()
                    pressed = false
                })
            },
        contentAlignment = Alignment.Center,
    ) {
        Text(label, fontSize = 20.sp, color = MaterialTheme.colorScheme.onSecondaryContainer.copy(alpha = if (enabled) 1f else 0.38f))
    }
}
