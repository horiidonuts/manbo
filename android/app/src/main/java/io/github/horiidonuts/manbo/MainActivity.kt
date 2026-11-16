package io.github.horiidonuts.manbo

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings as AndroidSettings
import android.view.HapticFeedbackConstants
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay

/** Montserrat (variable) at a given weight — the desktop app's font. */
private fun montserrat(weight: Int) = FontFamily(
    Font(R.font.montserrat, FontWeight(weight), variationSettings = FontVariation.Settings(FontVariation.weight(weight)))
)
val MontserratBold = montserrat(800)
val MontserratMedium = montserrat(500)

private const val HANDOFF_MS = 500L   // same beat as the desktop app

class MainActivity : ComponentActivity() {
    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) {}
    private var pendingCode: String? = null   // a scanned code, waiting for local network access
    private val askLocalNetwork = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        SyncLink.restart()
        val code = pendingCode.also { pendingCode = null }
        when {
            !granted -> toast("Manbo needs \"Nearby devices\" to find your PC")
            code != null -> usePairingCode(code)
            else -> scanPairingCode()
        }
    }

    /** "Scan code": Android 17 first asks for local network access, then Google's QR scanner opens. */
    private fun pairWithPc() {
        if (!hasLocalNetwork()) askLocalNetwork.launch(LOCAL_NETWORK) else scanPairingCode()
    }

    private fun hasLocalNetwork() =
        ContextCompat.checkSelfPermission(this, LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED

    private fun scanPairingCode() {
        val options = GmsBarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()
        GmsBarcodeScanning.getClient(this, options).startScan()
            .addOnSuccessListener { code -> code.rawValue?.let(::usePairingCode) }
            .addOnFailureListener {
                // no Google Play services (or the scanner won't load): the camera app works too
                toast("Couldn't open the scanner. Scan the code with your camera app instead.")
            }
    }

    private fun usePairingCode(code: String) {
        if (!hasLocalNetwork()) {
            pendingCode = code
            askLocalNetwork.launch(LOCAL_NETWORK)
            return
        }
        if (SyncStore.pair(code) == null) return toast("That isn't a Manbo pairing code")
        SyncLink.restart()
        SyncService.update(this)
    }

    /** Opened from a manbo://pair link (the camera app): ask first, a web page could link here too. */
    private fun handleLink(intent: Intent?) {
        val code = intent?.takeIf { it.action == Intent.ACTION_VIEW }?.dataString ?: return
        setIntent(Intent(this, MainActivity::class.java))   // don't ask again on rotation
        val name = android.net.Uri.parse(code).getQueryParameter("name") ?: "this computer"
        android.app.AlertDialog.Builder(this)
            .setTitle("Pair with $name?")
            .setMessage("Manbo will keep its timer in step with Manbo on $name.")
            .setPositiveButton("Pair") { _, _ -> usePairingCode(code) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun toast(text: String) = android.widget.Toast.makeText(this, text, android.widget.Toast.LENGTH_LONG).show()

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleLink(intent)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        TimerEngine.init(this)
        Notifications.createChannels(this)
        Sounds.init(this)
        volumeControlStream = android.media.AudioManager.STREAM_MUSIC   // volume keys set the media volume
        enableEdgeToEdge(SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT))
        if (Build.VERSION.SDK_INT >= 33) askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        setContent { ManboScreen(
            openDndAccess = { startActivity(Intent(AndroidSettings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)) },
            pairWithPc = ::pairWithPc,
        ) }
        if (savedInstanceState == null) handleLink(intent)
    }

    override fun onStart() {
        super.onStart()
        AppVisibility.visible = true
        TimerEngine.finishIfDue()   // time may have run out while we were away
        Notifications.clearSessionEnded(this)
        SyncLink.hold(this, "screen")
        SyncService.update(this)
    }

    override fun onStop() {
        AppVisibility.visible = false
        SyncLink.release("screen")
        super.onStop()
    }
}

@Composable
fun ManboScreen(openDndAccess: () -> Unit, pairWithPc: () -> Unit) {
    val context = LocalContext.current
    val view = LocalView.current
    val timer by TimerEngine.state.collectAsStateWithLifecycle()
    val settings by SettingsStore.state.collectAsStateWithLifecycle()
    var showSettings by remember { mutableStateOf(false) }

    // end of a session: the button pops and the clock rests at 00:00 for a beat, then the next session
    var handoffMode by remember { mutableStateOf<Mode?>(null) }
    LaunchedEffect(Unit) {
        TimerEngine.finished.collect { f ->
            handoffMode = f.finished   // (the chime itself comes from SessionEnd)
            view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        }
    }
    LaunchedEffect(handoffMode) {
        if (handoffMode != null) {
            delay(HANDOFF_MS)
            handoffMode = null
        }
    }
    LaunchedEffect(timer.running) { if (timer.running) handoffMode = null }

    // tick while running
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(timer.running, timer.endAt) {
        while (timer.running) {
            now = System.currentTimeMillis()
            if (now >= timer.endAt && AppVisibility.visible) TimerEngine.finishIfDue()   // off screen the alarm does it
            delay(100)
        }
    }
    LaunchedEffect(settings) { TimerEngine.onSettingsChanged() }

    val mode = handoffMode ?: timer.mode
    // read `now` so each tick recomposes, but count from the real clock: right after a start,
    // `now` is still from the last run and would make the time jump up for a frame
    val seconds = if (handoffMode != null) 0 else timer.remainingSeconds(maxOf(now, System.currentTimeMillis()))
    val pal = palette(settings.theme, mode)
    val bg by animateColorAsState(pal.bg, tween(450), label = "bg")
    val button by animateColorAsState(pal.button, tween(450), label = "button")
    val ink by animateColorAsState(pal.text, tween(450), label = "ink")

    // the button sounds follow the button: sink on start, pop when it comes up
    var wasDown by remember { mutableStateOf(timer.running) }
    LaunchedEffect(timer.running) {
        if (timer.running != wasDown && settings.buttonSounds) Sounds.play(if (timer.running) "press" else "pop")
        wasDown = timer.running
    }

    Box(Modifier.fillMaxSize().background(bg)) {
        Column(
            Modifier.fillMaxSize().safeDrawingPadding().padding(horizontal = 24.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                IconButton(onClick = { showSettings = true }) {
                    Icon(Icons.Filled.Settings, contentDescription = "Settings", tint = ink)
                }
            }
            Spacer(Modifier.height(8.dp))
            ModePill(mode, ink) { delta ->
                if (settings.buttonSounds) Sounds.play("tab")
                view.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK)
                handoffMode = null
                val modes = Mode.entries
                TimerEngine.select(modes[(modes.indexOf(timer.mode) + delta + modes.size) % modes.size])
            }
            Spacer(Modifier.height(28.dp))
            RollingTime(
                seconds = seconds,
                style = TextStyle(fontFamily = MontserratBold, fontSize = 84.sp, letterSpacing = (-1).sp,
                    fontFeatureSettings = "tnum"),
                color = ink,
                animate = settings.rollingDigits,
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val filled = timer.cyclePosition(settings.longBreakInterval)
                repeat(settings.longBreakInterval) { i ->
                    Box(Modifier.size(10.dp).background(if (i < filled) ink else ink.copy(alpha = 0.18f), CircleShape))
                }
            }
            PushButton3D(
                down = timer.running,
                bg = bg, face = button, ink = ink,
                onPress = {
                    view.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
                    handoffMode = null
                    TimerEngine.toggle()
                },
                modifier = Modifier.fillMaxWidth().weight(1f),
            )
            IconButton(onClick = { handoffMode = null; TimerEngine.reset() }, modifier = Modifier.size(56.dp)) {
                Icon(Icons.Filled.Refresh, contentDescription = "Reset session", tint = ink)
            }
            Spacer(Modifier.height(12.dp))
        }
    }

    if (showSettings) SettingsSheet(settings, ink, openDndAccess, pairWithPc, onDismiss = { showSettings = false })
}

@Composable
private fun ModePill(mode: Mode, ink: Color, onStep: (Int) -> Unit) {
    var drag by remember { mutableStateOf(0f) }
    Row(
        Modifier
            .border(1.dp, ink.copy(alpha = 0.18f), RoundedCornerShape(50))
            .background(Color.White.copy(alpha = 0.35f), RoundedCornerShape(50))
            .pointerInput(Unit) {
                detectHorizontalDragGestures(
                    onDragEnd = { if (kotlin.math.abs(drag) > 40) onStep(if (drag < 0) 1 else -1); drag = 0f },
                    onHorizontalDrag = { _, d -> drag += d },
                )
            }
            .height(40.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = { onStep(-1) }, Modifier.size(40.dp)) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Previous mode", tint = ink)
        }
        AnimatedContent(
            targetState = mode,
            transitionSpec = {
                val forward = targetState.ordinal > initialState.ordinal
                val dir = if (forward) 1 else -1
                slideInHorizontally(tween(280)) { it * dir } togetherWith slideOutHorizontally(tween(280)) { -it * dir }
            },
            label = "mode",
            modifier = Modifier.width(150.dp),
        ) { m ->
            Text(
                m.title,
                style = TextStyle(fontFamily = MontserratBold, fontSize = 13.sp, letterSpacing = 2.sp),
                color = ink,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        IconButton(onClick = { onStep(1) }, Modifier.size(40.dp)) {
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "Next mode", tint = ink)
        }
    }
}
