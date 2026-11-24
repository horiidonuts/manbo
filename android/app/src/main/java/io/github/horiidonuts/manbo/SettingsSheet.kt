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
import androidx.compose.runtime.key
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
import androidx.compose.foundation.layout.FlowRow
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
        ) { key(settings.language) {   // a new language: everything in here again, in it
            Heading(t("Timer", "Zamanlayıcı"))
            Stepper(t("Focus", "Odak"), t("minutes", "dakika"), settings.focusMinutes, Settings.RANGES.getValue("focusMinutes")) { v ->
                SettingsStore.update { it.copy(focusMinutes = v) }
            }
            Stepper(t("Short break", "Kısa mola"), t("minutes", "dakika"), settings.shortBreakMinutes, Settings.RANGES.getValue("shortBreakMinutes")) { v ->
                SettingsStore.update { it.copy(shortBreakMinutes = v) }
            }
            Stepper(t("Long break", "Uzun mola"), t("minutes", "dakika"), settings.longBreakMinutes, Settings.RANGES.getValue("longBreakMinutes")) { v ->
                SettingsStore.update { it.copy(longBreakMinutes = v) }
            }
            Stepper(t("Long break interval", "Uzun mola aralığı"), t("focus sessions", "odak seansı"), settings.longBreakInterval, Settings.RANGES.getValue("longBreakInterval")) { v ->
                SettingsStore.update { it.copy(longBreakInterval = v) }
            }

            Heading(t("Focus", "Odak"))
            Toggle(t("Do Not Disturb while focusing", "Odaklanırken Rahatsız Etmeyin"),
                t("Silence other notifications while a focus session runs", "Odak seansı sürerken diğer bildirimleri sustur"),
                settings.dndDuringFocus) { on ->
                if (on && !Dnd.hasAccess(context)) openDndAccess()   // Android asks once for DND access
                SettingsStore.update { it.copy(dndDuringFocus = on) }
            }

            Heading(t("PC sync", "Bilgisayarla senkron"))
            val pc = pairing
            if (pc == null) {
                Text(t("Keep the timer in step with Manbo on your computer: start, pause or skip on either one. " +
                    "On the PC open Preferences → Phone → Show code, then scan it here or with your camera app.",
                    "Zamanlayıcı bilgisayardaki Manbo ile birlikte çalışsın: ikisinden birinde başlat, duraklat ya da atla. " +
                    "Bilgisayarda Tercihler → Telefon → Kodu göster'i aç, sonra kodu burada ya da kamera uygulamasıyla tara."),
                    style = TextStyle(fontFamily = MontserratMedium, fontSize = 13.sp), color = Color.Gray)
                FilledTonalButton(onClick = pairWithPc) { Text(t("Scan code", "Kodu tara")) }
            } else {
                val state = when (link.state) {
                    SyncLink.State.CONNECTED -> t("Connected 💞", "Bağlı 💞")
                    SyncLink.State.NO_PERMISSION -> t("I need the \"Nearby devices\" permission 🙏",
                        "\"Yakındaki cihazlar\" izni lazım 🙏")
                    SyncLink.State.SEARCHING -> t("Looking for it 🔍 same Wi-Fi? Manbo open there?",
                        "Arıyorum 🔍 aynı ağda mısın? Manbo orada açık mı?")
                    else -> t("Not connected right now", "Şu an bağlı değil")
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
                    }) { Text(t("Unpair", "Eşleşmeyi kaldır")) }
                }
                if (link.state == SyncLink.State.NO_PERMISSION) {
                    FilledTonalButton(onClick = pairWithPc) { Text(t("Allow and scan again", "İzin ver ve tekrar tara")) }
                }
                Toggle(t("Stay connected in background", "Arka planda bağlı kal"),
                    t("So a session started on the PC starts here too (with Do Not Disturb). Shows a quiet notification.",
                        "Bilgisayarda başlayan seans burada da başlasın (Rahatsız Etmeyin ile). Sessiz bir bildirim gösterir."),
                    settings.syncInBackground) { on ->
                    SettingsStore.update { it.copy(syncInBackground = on) }
                    SyncService.update(context)
                }
            }

            Heading(t("Appearance", "Görünüm"))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (t in THEMES) {
                    FilterChip(selected = settings.theme == t.key, onClick = { SettingsStore.update { it.copy(theme = t.key) } },
                        label = { Text(t.name) })
                }
            }
            Toggle(t("Rolling digits", "Kayan rakamlar"),
                t("Digits roll as time passes and when the timer resets", "Rakamlar zaman geçtikçe ve zamanlayıcı sıfırlanınca kayar"),
                settings.rollingDigits) { on ->
                SettingsStore.update { it.copy(rollingDigits = on) }
            }

            Heading(t("Sound", "Ses"))
            Toggle(t("Button sounds", "Buton sesleri"),
                t("Clicks for the button and when switching modes", "Butona basınca ve mod değiştirince tık sesi"),
                settings.buttonSounds) { on ->
                SettingsStore.update { it.copy(buttonSounds = on) }
            }
            Text(t("Chime", "Zil"), style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (len in Settings.CHIME_LENGTHS) {
                    FilterChip(selected = settings.chimeLength == len, onClick = {
                        SettingsStore.update { it.copy(chimeLength = len) }
                        Sounds.chime(context, SettingsStore.value)
                    }, label = { Text(CHIME_NAMES.getValue(len)()) })
                }
            }
            Text(t("Chime volume · ${settings.chimeVolume}%", "Zil sesi · %${settings.chimeVolume}"), style = TextStyle(fontFamily = MontserratMedium, fontSize = 16.sp))
            Slider(
                value = settings.chimeVolume.toFloat(), valueRange = 0f..100f,
                enabled = settings.chimeLength != "off",
                onValueChange = { v -> SettingsStore.update { it.copy(chimeVolume = v.toInt()) } },
                onValueChangeFinished = { Sounds.chime(context, SettingsStore.value) },
            )

            Heading(t("Language", "Dil"))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (lang in Lang.LANGUAGES) {
                    FilterChip(selected = settings.language == lang, onClick = {
                        SettingsStore.update { it.copy(language = lang) }
                        Notifications.createChannels(context)   // channel names in the new language
                    }, label = { Text(LANGUAGE_NAMES.getValue(lang)()) })
                }
            }
        } }
    }
}

private val CHIME_NAMES = mapOf<String, () -> String>(
    "off" to { t("Off", "Kapalı") }, "short" to { t("Short", "Kısa") },
    "normal" to { t("Normal", "Normal") }, "long" to { t("Long", "Uzun") },
)

// each language in its own words, "system" in the current one
private val LANGUAGE_NAMES = mapOf<String, () -> String>(
    "system" to { t("System", "Sistem") }, "en" to { "English" }, "tr" to { "Türkçe" },
)

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
