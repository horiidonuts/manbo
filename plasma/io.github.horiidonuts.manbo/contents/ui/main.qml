/*
 * Manbo widget: shows and drives the running Manbo app over D-Bus
 * (io.github.horiidonuts.Manbo1, see manbo/service.py). The timer itself
 * lives in Manbo; the widget only counts down locally from EndTime and
 * follows PropertiesChanged.
 *
 * Panel: a small "● 24:59"; click opens the card, middle-click starts/pauses.
 * Desktop: the card itself — a little Manbo.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.workspace.dbus as DBus
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string service: "io.github.horiidonuts.Manbo"
    readonly property string objectPath: "/io/github/horiidonuts/Manbo"
    readonly property string iface: "io.github.horiidonuts.Manbo1"
    readonly property var modes: ["focus", "short", "long"]
    // Manbo's language (Preferences → Language) once it's running; the system's until then
    property string lang: Qt.locale().name.startsWith("tr") ? "tr" : "en"
    onManboStateChanged: if (manboState && manboState.language) lang = manboState.language
    readonly property bool turkish: lang === "tr"
    function t(en, tr) { return turkish ? tr : en }
    readonly property var modeTitles: turkish ? ({focus: "ODAK", short: "KISA MOLA", long: "UZUN MOLA"})
        : ({focus: "FOCUS", short: "SHORT BREAK", long: "LONG BREAK"})
    readonly property var modeNames: turkish ? ({focus: "Odak", short: "Kısa mola", long: "Uzun mola"})
        : ({focus: "Focus", short: "Short break", long: "Long break"})
    // shown while Manbo isn't running (Blossom / focus)
    readonly property var fallbackPalette: ({bg: "#FFE5D9", button: "#F4ACB7", text: "#7E6770"})

    DBus.DBusServiceWatcher {
        id: watcher
        busType: DBus.BusType.Session
        watchedService: root.service
    }

    // The whole state as JSON: GetState() once Manbo is up, then every
    // StateChanged signal. (Plasma's DBus.Properties drops some variant values.)
    property var manboState: null
    property var pendingState: null   // the next session, shown after the handoff
    function applyState(json) {
        let next
        try {
            next = JSON.parse(json)
        } catch (e) {
            console.warn("manbo widget: bad state", json, e)
            return
        }
        const prev = root.manboState
        handoff.stop()
        if (prev && prev.running && !next.running && prev.mode !== next.mode) {
            // a session just ended: like the app, show it at 00:00 for a beat
            // (the button pops), then move on to the next one
            root.manboState = Object.assign({}, prev, {running: false, remaining: 0, endTime: 0,
                                                       cyclePosition: next.cyclePosition})
            root.pendingState = next
            handoff.start()
            return
        }
        root.pendingState = null
        root.manboState = next
    }
    Timer {
        id: handoff
        interval: 500   // HANDOFF_MS in manbo/window.py
        onTriggered: {
            root.manboState = root.pendingState
            root.pendingState = null
        }
    }
    function fetchState() {
        DBus.SessionBus.asyncCall({
            service: root.service, path: root.objectPath, iface: root.iface,
            member: "GetState", arguments: [], signature: "",
        }, reply => root.applyState(typeof reply === "string" ? reply : reply.value),
           error => root.manboState = null)
    }
    Connections {
        target: watcher
        function onRegisteredChanged() {
            if (watcher.registered) root.fetchState()
            else root.manboState = null
        }
    }
    Component.onCompleted: if (watcher.registered) fetchState()

    DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: root.service
        path: root.objectPath
        iface: root.iface
        enabled: watcher.registered
        function dbusStateChanged(json) { root.applyState(json) }
    }

    readonly property var p: manboState
    readonly property bool connected: watcher.registered && manboState !== null
    readonly property string mode: connected ? p.mode : "focus"
    readonly property bool running: connected && p.running
    readonly property var palette: connected ? p.palette : fallbackPalette
    readonly property int interval: connected ? p.longBreakInterval : 4
    readonly property int cyclePosition: connected ? p.cyclePosition : 0
    readonly property int completed: connected ? p.completedSessions : 0

    property double now: Date.now()
    Timer {
        interval: 200
        repeat: true
        running: root.running
        onTriggered: root.now = Date.now()
    }
    readonly property int remaining: !connected ? 25 * 60
        : running ? Math.max(0, Math.ceil((p.endTime - now) / 1000))
        : p.remaining
    readonly property string timeText: {
        const m = Math.floor(remaining / 60), s = remaining % 60
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }

    function call(member, args, signature) {
        DBus.SessionBus.asyncCall({
            service: root.service, path: root.objectPath, iface: root.iface,
            member: member, arguments: args || [], signature: signature || "",
        })
    }
    function toggle() { connected ? call("Toggle") : openApp() }
    function reset() { if (connected) call("Reset") }
    function stepMode(delta) {
        if (!connected) return openApp()
        const i = (modes.indexOf(mode) + delta + modes.length) % modes.length
        call("SelectMode", [modes[i]], "s")
    }
    // Starts Manbo through D-Bus activation if it isn't running, and shows it.
    function openApp() {
        DBus.SessionBus.asyncCall({
            service: root.service, path: root.objectPath,
            iface: "org.freedesktop.Application", member: "Activate",
            arguments: [{}], signature: "a{sv}",
        })
    }

    Plasmoid.icon: "io.github.horiidonuts.Manbo"
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    toolTipMainText: connected ? "Manbo · " + modeNames[mode] : "Manbo"
    toolTipSubText: !connected ? t("Not running — click to open", "Çalışmıyor — açmak için tıkla")
        : turkish ? (running ? "Çalışıyor" : "Duraklatıldı") + " · " + timeText + " kaldı · odak seansı "
                    + cyclePosition + "/" + interval
        : (running ? "Running" : "Paused") + " · " + timeText + " left · "
          + cyclePosition + " of " + interval + " focus sessions"

    // compact in panels, the card everywhere else (desktop, standalone window)
    readonly property bool inPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
        || Plasmoid.formFactor === PlasmaCore.Types.Vertical
    preferredRepresentation: inPanel ? compactRepresentation : fullRepresentation

    compactRepresentation: CompactView { widget: root }
    fullRepresentation: Card { widget: root }
}
