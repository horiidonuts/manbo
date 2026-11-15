"""Manbo's D-Bus API, for widgets, scripts and (later) phone sync.

Exported by the running app on its own bus name (io.github.horiidonuts.Manbo)
at /io/github/horiidonuts/Manbo, interface io.github.horiidonuts.Manbo1.

Clients should not poll: read the properties once, then follow
PropertiesChanged (sent on every state change, not every second) and count
down locally from EndTime.

    gdbus call --session --dest io.github.horiidonuts.Manbo \\
        --object-path /io/github/horiidonuts/Manbo \\
        --method io.github.horiidonuts.Manbo1.Toggle
"""

import json

from gi.repository import Gio, GLib

from .themes import palette
from .timer import MODES

IFACE = "io.github.horiidonuts.Manbo1"

XML = f"""
<node>
  <interface name="{IFACE}">
    <!-- "focus", "short" or "long" -->
    <property name="Mode" type="s" access="read"/>
    <property name="Running" type="b" access="read"/>
    <!-- seconds left, as of the last change (count down from EndTime instead) -->
    <property name="Remaining" type="u" access="read"/>
    <!-- wall clock (Unix ms) when the session ends; 0 while not running -->
    <property name="EndTime" type="x" access="read"/>
    <!-- full length of the current session, seconds -->
    <property name="Duration" type="u" access="read"/>
    <property name="CompletedSessions" type="u" access="read"/>
    <!-- focus sessions done in the current long-break cycle, out of LongBreakInterval -->
    <property name="CyclePosition" type="u" access="read"/>
    <property name="LongBreakInterval" type="u" access="read"/>
    <!-- colors of the current theme + mode: "bg", "button", "text" (#rrggbb) -->
    <property name="Palette" type="a{{ss}}" access="read"/>
    <!-- goes up by one on every change: the newest state wins when syncing -->
    <property name="Version" type="t" access="read"/>
    <method name="Toggle"/>
    <method name="Start"/>
    <method name="Pause"/>
    <method name="Reset"/>
    <method name="SelectMode"><arg name="mode" type="s" direction="in"/></method>
    <!-- the whole state as one JSON object (camelCase keys of the properties
         above), for clients whose D-Bus layer struggles with variants (QML) -->
    <method name="GetState"><arg name="state" type="s" direction="out"/></method>
    <signal name="StateChanged"><arg name="state" type="s"/></signal>
    <signal name="Finished">
      <arg name="finished" type="s"/>
      <arg name="next" type="s"/>
    </signal>
  </interface>
</node>
"""

_TYPES = {
    "Mode": "s", "Running": "b", "Remaining": "u", "EndTime": "x",
    "Duration": "u", "CompletedSessions": "u", "CyclePosition": "u",
    "LongBreakInterval": "u", "Palette": "a{ss}", "Version": "t",
}


class ManboService:
    def __init__(self, connection, path, timer, settings, keep_alive):
        """`keep_alive()` makes sure the app stays up: when D-Bus activation
        started Manbo just to run a method, there is no window holding it yet."""
        self._conn = connection
        self._path = path
        self._timer = timer
        self._settings = settings
        self._keep_alive = keep_alive
        self._version = 0
        self._last = {}
        info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
        # register_object_with_closures2 is GLib >= 2.84 (e.g. not Ubuntu 24.04)
        register = getattr(connection, "register_object_with_closures2", None) or connection.register_object
        self._reg_id = register(path, info, self._on_method, self._on_get_property, None)
        timer.connect("changed", lambda *_: self._on_changed())
        timer.connect("finished", self._on_finished)
        settings.connect("changed", lambda *_: self._on_changed())
        self._last = self._snapshot()

    def unregister(self):
        if self._reg_id:
            self._conn.unregister_object(self._reg_id)
            self._reg_id = 0

    # -- state -----------------------------------------------------------------

    def _snapshot(self):
        t = self._timer
        remaining_ms = t.remaining_us // 1000
        end = GLib.get_real_time() // 1000 + remaining_ms if t.running else 0
        return {
            "Mode": t.mode,
            "Running": t.running,
            "Remaining": t.remaining_seconds,
            "EndTime": end,
            "Duration": t.duration_seconds,
            "CompletedSessions": t.completed,
            "CyclePosition": t.cycle_position,
            "LongBreakInterval": self._settings["long_break_interval"],
            "Palette": dict(palette(self._settings["theme"], t.mode)),
            "Version": self._version,
        }

    def _on_changed(self):
        now = self._snapshot()
        changed = {k: v for k, v in now.items() if k != "Version" and self._last.get(k) != v}
        if not changed:
            return
        self._version += 1
        now["Version"] = self._version
        changed = {k: GLib.Variant(_TYPES[k], now[k]) for k in [*changed, "Version"]}
        self._last = now
        self._emit("org.freedesktop.DBus.Properties", "PropertiesChanged",
                   GLib.Variant("(sa{sv}as)", (IFACE, changed, [])))
        self._emit(IFACE, "StateChanged", GLib.Variant("(s)", (_to_json(now),)))

    def _on_finished(self, _timer, finished, nxt):
        self._emit(IFACE, "Finished", GLib.Variant("(ss)", (finished, nxt)))

    def _emit(self, iface, name, params):
        try:
            self._conn.emit_signal(None, self._path, iface, name, params)
        except GLib.Error as e:
            print(f"manbo: D-Bus signal failed: {e.message}")

    # -- D-Bus handlers ----------------------------------------------------------

    def _on_get_property(self, _conn, _sender, _path, _iface, name):
        return GLib.Variant(_TYPES[name], self._snapshot()[name])

    def _on_method(self, _conn, _sender, _path, _iface, method, params, invocation):
        t = self._timer
        if method == "GetState":
            invocation.return_value(GLib.Variant("(s)", (_to_json(self._snapshot()),)))
            return
        self._keep_alive()
        if method == "SelectMode":
            mode = params.unpack()[0]
            if mode not in MODES:
                invocation.return_dbus_error(f"{IFACE}.Error.InvalidMode",
                                             f"mode must be one of {', '.join(MODES)}")
                return
            t.select(mode)
        else:
            {"Toggle": t.toggle, "Start": t.start, "Pause": t.pause, "Reset": t.reset}[method]()
        invocation.return_value(None)


def _to_json(state):
    """{"Mode": ...} -> '{"mode": ...}'"""
    return json.dumps({k[0].lower() + k[1:]: v for k, v in state.items()}, separators=(",", ":"))
