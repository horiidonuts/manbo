package io.github.horiidonuts.manbo

import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.os.Build
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.provider.Settings as AndroidSettings
import android.util.Base64
import android.util.Log
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

private const val HISTORY_CHUNK = 250   // sessions per history message, well under the PC's line limit
private const val PORT = 47250
private const val PING_MS = 30_000L     // the PC answers each ping...
private const val SILENCE_MS = 75_000   // ...so this long without a word means it's gone
private const val SWEEP_MIN_PREFIX = 22 // ask every address on networks up to /22 (1022 hosts)
private const val MAX_BACKOFF_MS = 30_000L
// hotspot (Samsung: swlan0), USB and Bluetooth tethering; not rmnet (mobile data) or tun (VPN)
private val TETHER_PREFIXES = listOf("swlan", "ap", "softap", "wlan", "rndis", "usb", "ncm", "bt-pan", "eth")

// Sync with Manbo on a PC over the LAN. The PC is the server (manbo/sync.py has the protocol);
// the phone pairs by scanning its QR code and then keeps connecting to it.

private const val TAG = "ManboSync"
const val LOCAL_NETWORK = "android.permission.ACCESS_LOCAL_NETWORK"   // Android 17

/** Android 17 (API 37) asks for local network access; older versions don't have the permission. */
fun hasLocalNetwork(context: Context) = Build.VERSION.SDK_INT < 37 ||
    ContextCompat.checkSelfPermission(context, LOCAL_NETWORK) == PackageManager.PERMISSION_GRANTED

data class Pairing(
    val pcId: String,
    val name: String,
    val key: ByteArray,
    val port: Int,
    val addresses: List<String>,   // from the QR code; the last one that worked comes first
)

object SyncStore {
    private lateinit var prefs: SharedPreferences
    private val _pairing = MutableStateFlow<Pairing?>(null)
    val pairing: StateFlow<Pairing?> = _pairing

    /** This phone's id (the `by` of its changes). */
    lateinit var me: String
        private set

    fun init(context: Context) {
        if (::prefs.isInitialized) return
        prefs = context.applicationContext.getSharedPreferences("sync", Context.MODE_PRIVATE)
        me = prefs.getString("me", null) ?: UUID.randomUUID().toString().replace("-", "").also {
            prefs.edit().putString("me", it).apply()
        }
        _pairing.value = load()
    }

    private fun load(): Pairing? {
        val id = prefs.getString("pc_id", null) ?: return null
        return Pairing(
            pcId = id,
            name = prefs.getString("pc_name", "PC") ?: "PC",
            key = Base64.decode(prefs.getString("key", "") ?: "", Base64.URL_SAFE or Base64.NO_PADDING),
            port = prefs.getInt("port", 47250),
            addresses = (prefs.getString("addresses", "") ?: "").split(',').filter { it.isNotBlank() },
        )
    }

    private fun save(p: Pairing) {
        prefs.edit()
            .putString("pc_id", p.pcId)
            .putString("pc_name", p.name)
            .putString("key", Base64.encodeToString(p.key, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP))
            .putInt("port", p.port)
            .putString("addresses", p.addresses.joinToString(","))
            .apply()
        _pairing.value = p
    }

    /** A scanned manbo://pair code; null if it isn't one. */
    fun pair(text: String): Pairing? {
        val uri = Uri.parse(text)
        if (uri.scheme != "manbo" || uri.host != "pair") return null
        val p = runCatching {
            Pairing(
                pcId = uri.getQueryParameter("id")!!,
                name = uri.getQueryParameter("name") ?: "PC",
                key = Base64.decode(uri.getQueryParameter("key")!!, Base64.URL_SAFE or Base64.NO_PADDING),
                port = uri.getQueryParameter("port")?.toInt() ?: 47250,
                addresses = (uri.getQueryParameter("ip") ?: "").split(',').filter { it.isNotBlank() },
            )
        }.getOrNull() ?: return null
        if (p.key.size < 16) return null
        save(p)
        return p
    }

    fun unpair() {
        prefs.edit().remove("pc_id").remove("pc_name").remove("key").remove("port").remove("addresses").apply()
        _pairing.value = null
    }

    /** Found the PC at [address]: try it first next time. */
    fun worked(address: String, port: Int) {
        val p = _pairing.value ?: return
        if (p.addresses.firstOrNull() == address && p.port == port) return
        save(p.copy(port = port, addresses = listOf(address) + (p.addresses - address)))
    }
}

object SyncLink {
    enum class State { UNPAIRED, IDLE, NO_PERMISSION, SEARCHING, CONNECTED }
    data class Status(val state: State, val pc: String = "")

    private val _status = MutableStateFlow(Status(State.IDLE))
    val status: StateFlow<Status> = _status
    /** Live link to the PC right now? (Then the PC plays the chime.) */
    val connected get() = _status.value.state == State.CONNECTED

    private lateinit var app: Context
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val holders = mutableSetOf<String>()
    private var job: Job? = null
    @Volatile private var socket: Socket? = null
    private val wake = Channel<Unit>(Channel.CONFLATED)
    private var watchingNetwork = false
    @Volatile private var backoff = 3_000L

    /** Wi-Fi/Ethernet networks we're on, newest last. The PC is on one of them, not on mobile data. */
    private val lans = LinkedHashMap<Network, LinkProperties?>()
    /** The LAN [socket] was opened on (network + its addresses): changes mean reconnect. */
    @Volatile private var socketLan: String? = null

    /** [who] (the screen, the background service) wants the link up. */
    @Synchronized
    fun hold(context: Context, who: String) {
        app = context.applicationContext
        holders += who
        watchNetwork()
        if (job?.isActive != true) job = scope.launch { loop() } else wake.trySend(Unit)
    }

    @Synchronized
    fun release(who: String) {
        holders -= who
        if (holders.isEmpty()) stop()
    }

    /** Pairing or permission changed: start over. */
    @Synchronized
    fun restart() {
        if (holders.isEmpty()) return
        stop()
        job = scope.launch { loop() }
    }

    private fun stop() {
        job?.cancel()
        job = null
        runCatching { socket?.close() }   // unblocks a read in progress
        _status.value = Status(if (SyncStore.pairing.value == null) State.UNPAIRED else State.IDLE)
    }

    private fun watchNetwork() {
        if (watchingNetwork) return
        watchingNetwork = true
        val cm = app.getSystemService(ConnectivityManager::class.java)
        // Wi-Fi without internet still counts: that's where the PC is. The default network may then
        // be mobile data, which can't reach it, so LAN sockets are bound to the Wi-Fi network itself.
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .addTransportType(NetworkCapabilities.TRANSPORT_ETHERNET)
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        synchronized(lans) {   // what we're on now, so the first callbacks aren't news
            @Suppress("DEPRECATION")
            for (n in cm.allNetworks) {
                val caps = cm.getNetworkCapabilities(n) ?: continue
                if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET))
                    lans[n] = cm.getLinkProperties(n)
            }
        }
        cm.registerNetworkCallback(request, object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = lanChanged { lans[network] = cm.getLinkProperties(network) }
            override fun onLinkPropertiesChanged(network: Network, lp: LinkProperties) = lanChanged { lans[network] = lp }
            override fun onLost(network: Network) = lanChanged { lans.remove(network) }
        })
        // the default network too: a VPN coming up changes the way to a Tailscale address
        cm.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { backoff = 3_000; wake.trySend(Unit) }
        })
    }

    /** Joined, left or got a new address on a Wi-Fi network: drop a link made on the old one and look again. */
    private fun lanChanged(change: () -> Unit) {
        val (before, now) = synchronized(lans) { lanKey().let { b -> change(); b to lanKey() } }
        if (before == now) return
        backoff = 3_000
        wake.trySend(Unit)
        val s = socket
        if (s != null && socketLan != now) {
            Log.i(TAG, "network changed, reconnecting")
            runCatching { s.close() }
        }
    }

    private fun lan(): Pair<Network, LinkProperties?>? = synchronized(lans) { lans.entries.lastOrNull()?.toPair() }

    private fun lanKey(): String? = lan()?.let { (n, lp) ->
        "$n|" + lp?.linkAddresses?.map { it.address }?.filterIsInstance<Inet4Address>()?.joinToString(",")
    }

    private suspend fun sleep(ms: Long) { withTimeoutOrNull(ms) { wake.receive() } }

    private suspend fun loop() {
        backoff = 3_000L
        while (currentCoroutineContext().isActive) {
            val p = SyncStore.pairing.value ?: run { _status.value = Status(State.UNPAIRED); return }
            if (!hasLocalNetwork(app)) {
                _status.value = Status(State.NO_PERMISSION, p.name)
                sleep(60_000)
                continue
            }
            if (_status.value.state != State.SEARCHING) _status.value = Status(State.SEARCHING, p.name)
            val s = connect(p)
            if (s == null) {
                sleep(backoff)
                backoff = minOf(backoff * 2, MAX_BACKOFF_MS)
                continue
            }
            backoff = 3_000
            socket = s
            Log.i(TAG, "connected to ${p.name} at ${s.inetAddress.hostAddress}")
            try {
                session(s, p)
            } catch (e: Exception) {
                if (currentCoroutineContext().isActive) Log.i(TAG, "link to ${p.name} lost: $e")
            } finally {
                runCatching { s.close() }
                socket = null
            }
            if (currentCoroutineContext().isActive) _status.value = Status(State.SEARCHING, p.name)
            sleep(2_000)
        }
    }

    private fun connect(p: Pairing): Socket? {
        val key = lanKey()
        val lan = lan()
        val tether = tetherSubnets(lan?.second?.interfaceName)
        for (address in p.addresses) tryConnect(address, p.port, lan?.first, tether)?.let { socketLan = key; return it }
        val (address, port) = discover(p, lan, tether) ?: return null
        return tryConnect(address, port, lan?.first, tether)?.also { socketLan = key }
    }

    /** A Tailscale-style (100.64.0.0/10) address goes through the VPN, i.e. the default network. */
    private fun isCgnat(address: String) = address.split('.').let {
        it.size == 4 && it[0] == "100" && (it[1].toIntOrNull() ?: 0) in 64..127
    }

    /**
     * LAN addresses go out on the Wi-Fi network; Tailscale ones and the PC on this phone's hotspot
     * through an unbound socket (Android routes those: the VPN, and its local_network table).
     */
    private fun tryConnect(address: String, port: Int, lan: Network?, tether: List<Subnet>): Socket? = try {
        val viaLan = lan != null && !isCgnat(address) && tether.none { address in it }
        val s = if (viaLan) lan!!.socketFactory.createSocket() else Socket()
        try {
            s.connect(InetSocketAddress(address, port), 2_500)
            s.tcpNoDelay = true
            s.keepAlive = true
        } catch (e: Exception) {
            runCatching { s.close() }
            throw e
        }
        SyncStore.worked(address, port)
        s
    } catch (e: Exception) {
        null
    }

    /** An IPv4 network one of our interfaces is on. */
    class Subnet(private val ip: Int, private val prefix: Int) {
        private val mask = if (prefix == 0) 0 else -1 shl (32 - prefix)
        private val net = ip and mask
        val broadcast: InetAddress get() = ipv4(net or mask.inv())
        /** Everyone else on it, if it's small enough to ask one by one. */
        val others: List<InetAddress>
            get() = if (prefix !in SWEEP_MIN_PREFIX..30) emptyList()
                else (net + 1 until (net or mask.inv())).filter { it != ip }.map(::ipv4)

        operator fun contains(address: String): Boolean {
            val a = runCatching { InetAddress.getByName(address) }.getOrNull() as? Inet4Address ?: return false
            return toInt(a) and mask == net
        }

        companion object {
            fun of(a: InetAddress?, prefix: Int) = (a as? Inet4Address)?.let { Subnet(toInt(it), prefix.toInt()) }
            private fun toInt(a: Inet4Address) = a.address.fold(0) { acc, b -> (acc shl 8) or (b.toInt() and 0xff) }
            private fun ipv4(v: Int): InetAddress = InetAddress.getByAddress(
                byteArrayOf((v ushr 24).toByte(), (v ushr 16).toByte(), (v ushr 8).toByte(), v.toByte()))
        }
    }

    /**
     * Networks this phone serves: its hotspot (and USB/Bluetooth tethering). Android doesn't list them
     * as networks, so they come from the interfaces. Mobile data and VPNs are left out by name.
     */
    private fun tetherSubnets(wifiInterface: String?): List<Subnet> = runCatching {
        java.net.NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback && it.name != wifiInterface &&
                TETHER_PREFIXES.any(it.name::startsWith) }
            .flatMap { i -> i.interfaceAddresses.mapNotNull { Subnet.of(it.address, it.networkPrefixLength.toInt()) } }
    }.getOrDefault(emptyList())

    /**
     * Ask around where the PC is now (its address changes with the network, or when the router hands
     * out a new one): on the Wi-Fi network, and on this phone's hotspot. Plenty of routers drop
     * broadcasts between devices, so besides the broadcast this asks every address directly: a few KB.
     */
    private fun discover(p: Pairing, lan: Pair<Network, LinkProperties?>?, tether: List<Subnet>): Pair<String, Int>? {
        val all = InetAddress.getByName("255.255.255.255")
        if (lan != null) {
            val subnets = lan.second?.linkAddresses.orEmpty().mapNotNull { Subnet.of(it.address, it.prefixLength) }
            ask(p, lan.first, listOf(all) + subnets.map { it.broadcast }, subnets.flatMap { it.others })?.let { return it }
        }
        if (tether.isNotEmpty() || lan == null) {
            val b = tether.map { it.broadcast } + if (lan == null) listOf(all) else emptyList()
            ask(p, null, b, tether.flatMap { it.others })?.let { return it }
        }
        return null
    }

    private fun ask(p: Pairing, network: Network?, broadcasts: List<InetAddress>, hosts: List<InetAddress>): Pair<String, Int>? = try {
        DatagramSocket().use { udp ->
            network?.bindSocket(udp)
            udp.broadcast = true
            val ask = JSONObject().put("t", "find").put("id", p.pcId).toString().toByteArray()
            fun send(to: List<InetAddress>) {
                for (a in to) runCatching { udp.send(DatagramPacket(ask, ask.size, a, PORT)) }
            }
            val buf = ByteArray(1024)
            val packet = DatagramPacket(buf, buf.size)
            // Wi-Fi loses packets: a second round (broadcasts only, the sweep is already out there)
            for (round in 0..1) {
                send(if (round == 0) broadcasts + hosts else broadcasts)
                val until = System.currentTimeMillis() + 1_500
                while (true) {
                    val left = until - System.currentTimeMillis()
                    if (left <= 0) break
                    udp.soTimeout = left.toInt()
                    packet.length = buf.size   // receive() shrinks it to the last packet
                    try {
                        udp.receive(packet)
                    } catch (e: java.net.SocketTimeoutException) {
                        break
                    }
                    val reply = runCatching { JSONObject(String(packet.data, 0, packet.length)) }.getOrNull() ?: continue
                    if (reply.optString("t") == "here" && reply.optString("id") == p.pcId) {
                        Log.i(TAG, "found ${p.name} at ${packet.address.hostAddress}")
                        return@use packet.address.hostAddress!! to reply.getInt("port")
                    }
                }
            }
            null
        }
    } catch (e: Exception) {
        Log.i(TAG, "discovery failed: $e")
        null
    }

    private suspend fun session(s: Socket, p: Pairing) {
        s.soTimeout = 10_000
        val reader = s.getInputStream().bufferedReader()
        val writer = s.getOutputStream().bufferedWriter()
        fun send(o: JSONObject) = synchronized(writer) {
            writer.write(o.toString())
            writer.write("\n")
            writer.flush()
        }

        // prove to each other that we hold the key from the QR code
        val n1 = nonce()
        send(JSONObject().put("t", "hello").put("id", p.pcId).put("phone", SyncStore.me)
            .put("name", deviceName()).put("nonce", n1))
        val challenge = JSONObject(reader.readLine() ?: return)
        val n2 = challenge.getString("nonce")
        if (challenge.optString("t") != "challenge" ||
            !MessageDigest.isEqual(challenge.getString("proof").toByteArray(), proof(p.key, "pc", n1, n2).toByteArray())
        ) {
            Log.w(TAG, "${p.name} didn't prove it has the key")
            return
        }
        send(JSONObject().put("t", "auth").put("proof", proof(p.key, "phone", n1, n2)))
        s.soTimeout = SILENCE_MS
        // our stars, all of them once (the PC merges them with its own and sends us its own)
        for (chunk in HistoryStore.sessions.value.chunked(HISTORY_CHUNK)) send(historyMessage(chunk))

        coroutineScope {
            // a failed write closes the socket, which ends the read below
            val sender = launch {
                try {
                    combine(TimerEngine.state, SettingsStore.state) { _, _ -> }.collect { send(stateMessage()) }
                } catch (e: Exception) {
                    runCatching { s.close() }
                    throw e
                }
            }
            val stars = launch {
                try {
                    HistoryStore.added.collect { send(historyMessage(it)) }
                } catch (e: Exception) {
                    runCatching { s.close() }
                    throw e
                }
            }
            val pinger = launch {
                try {
                    while (isActive) {
                        delay(PING_MS)
                        send(JSONObject().put("t", "ping"))
                    }
                } catch (e: Exception) {
                    runCatching { s.close() }
                    throw e
                }
            }
            try {
                while (true) {
                    val line = runInterruptible { reader.readLine() } ?: break
                    val m = JSONObject(line)
                    when (m.optString("t")) {
                        "state" -> withContext(Dispatchers.Main) { applyRemote(m) }
                        "history" -> m.optJSONArray("sessions")?.let(HistoryStore::merge)
                    }
                    if (_status.value.state != State.CONNECTED) _status.value = Status(State.CONNECTED, p.name)
                }
            } finally {
                sender.cancel()
                stars.cancel()
                pinger.cancel()
            }
        }
    }

    // -- state -----------------------------------------------------------------------

    private fun historyMessage(list: List<Session>) =
        JSONObject().put("t", "history").put("sessions", HistoryStore.toJson(list))

    private fun stateMessage(): JSONObject {
        val t = TimerEngine.value
        val s = SettingsStore.value
        return JSONObject().put("t", "state")
            .put("timer", JSONObject()
                .put("mode", t.mode.key).put("running", t.running).put("endAt", if (t.running) t.endAt else 0)
                .put("remainingMs", t.remainingMs()).put("started", t.started).put("completed", t.completed)
                .put("stamp", t.stamp).put("by", t.by))
            .put("durations", JSONObject()
                .put("focus", s.focusMinutes).put("short", s.shortBreakMinutes).put("long", s.longBreakMinutes)
                .put("interval", s.longBreakInterval).put("stamp", s.durStamp).put("by", s.durBy))
    }

    private fun newer(stamp: Long, by: String, thanStamp: Long, thanBy: String) =
        stamp > thanStamp || (stamp == thanStamp && by > thanBy)

    private fun applyRemote(m: JSONObject) {
        m.optJSONObject("durations")?.let { d ->
            val cur = SettingsStore.value
            val stamp = d.getLong("stamp")
            val by = d.getString("by")
            if (newer(stamp, by, cur.durStamp, cur.durBy)) {
                fun v(key: String, range: String) = d.getInt(key).coerceIn(Settings.RANGES.getValue(range))
                SettingsStore.update {
                    it.copy(
                        focusMinutes = v("focus", "focusMinutes"), shortBreakMinutes = v("short", "shortBreakMinutes"),
                        longBreakMinutes = v("long", "longBreakMinutes"), longBreakInterval = v("interval", "longBreakInterval"),
                        durStamp = stamp, durBy = by,
                    )
                }
                TimerEngine.onSettingsChanged()
            }
        }
        m.optJSONObject("timer")?.let { t ->
            val mode = Mode.entries.firstOrNull { it.key == t.optString("mode") } ?: return
            val remote = TimerState(
                mode = mode,
                running = t.getBoolean("running"),
                endAt = t.getLong("endAt"),
                remainingMs = t.getLong("remainingMs").coerceAtLeast(0),
                started = t.getBoolean("started"),
                completed = t.getInt("completed").coerceAtLeast(0),
                stamp = t.getLong("stamp"),
                by = t.getString("by"),
            )
            // the PC ended the session we're both running: end it here too
            val mine = TimerEngine.value
            if (mine.running && !remote.running && remote.stamp == mine.endAt) TimerEngine.finishIfDue(force = true)
            val now = TimerEngine.value
            if (newer(remote.stamp, remote.by, now.stamp, now.by)) TimerEngine.applyRemote(remote)
        }
    }

    // -- helpers ---------------------------------------------------------------------

    private fun nonce() = ByteArray(16).also { SecureRandom().nextBytes(it) }.joinToString("") { "%02x".format(it) }

    private fun proof(key: ByteArray, who: String, n1: String, n2: String): String {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(key, "HmacSHA256"))
        return mac.doFinal("manbo1|$who|$n1|$n2".toByteArray()).joinToString("") { "%02x".format(it) }
    }

    private fun deviceName() =
        AndroidSettings.Global.getString(app.contentResolver, AndroidSettings.Global.DEVICE_NAME)
            ?: android.os.Build.MODEL
}

/** Keeps the link to the PC up while Manbo is closed, so a session started there starts here too. */
class SyncService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onBind(intent: Intent?) = null

    override fun onCreate() {
        super.onCreate()
        TimerEngine.init(this)
        Notifications.createChannels(this)
        try {
            ServiceCompat.startForeground(this, Notifications.ID_SYNC, Notifications.syncNotification(this, SyncLink.status.value),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } catch (e: Exception) {   // not allowed right now (started from the background)
            Log.w(TAG, "can't run in the background: $e")
            stopSelf()
            return
        }
        SyncLink.hold(this, "service")
        scope.launch {
            SyncLink.status.collect { st ->
                if (st.state == SyncLink.State.UNPAIRED) stopSelf()
                else Notifications.showSync(this@SyncService, st)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int) = START_STICKY

    override fun onDestroy() {
        scope.cancel()
        SyncLink.release("service")
        super.onDestroy()
    }

    companion object {
        /** Run the service if the phone is paired and the user wants it; stop it otherwise. */
        fun update(context: Context) {
            val want = SyncStore.pairing.value != null && SettingsStore.value.syncInBackground
            val intent = Intent(context, SyncService::class.java)
            if (!want) {
                context.stopService(intent)
                return
            }
            try {
                ContextCompat.startForegroundService(context, intent)
            } catch (e: Exception) {
                Log.w(TAG, "can't start the sync service: $e")
            }
        }
    }
}

/** After a reboot or an update: back to syncing, and the running session's alarm back on. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        TimerEngine.init(context)
        TimerEngine.restore()
        SyncService.update(context)
    }
}
