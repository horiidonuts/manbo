"""Do Not Disturb while a focus session runs (optional).

Asks the desktop's notification server to hold back notifications
(org.freedesktop.Notifications.Inhibit — KDE Plasma supports it) while a
focus session is running, and lets them through again on pause, break or
quit. The server also drops the inhibition by itself if Manbo exits.
"""

from gi.repository import Gio, GLib

from . import APP_ID
from .timer import FOCUS

NOTIFICATIONS = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"
TIMEOUT_MS = 2000


class FocusDnd:
    def __init__(self, timer, settings):
        self._timer = timer
        self._settings = settings
        self._cookie = None     # inhibition held
        self._pending = False   # Inhibit call in flight
        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        except GLib.Error:
            self._bus = None
        # Connected before any window: on "finished" the inhibition is lifted
        # before the window sends its session-finished notification.
        timer.connect("finished", lambda *_: self._update())
        timer.connect("changed", lambda *_: self._update())
        settings.connect("changed", lambda _s, key: key == "dnd_during_focus" and self._update())

    @property
    def wanted(self):
        return (self._settings["dnd_during_focus"]
                and self._timer.running and self._timer.mode == FOCUS)

    def _update(self):
        if self._bus is None or self._pending:
            return  # the reply handler re-checks
        if self.wanted and self._cookie is None:
            self._pending = True
            self._call("Inhibit", GLib.Variant("(ssa{sv})", (APP_ID, "Focus session", {})),
                       GLib.VariantType("(u)"), self._on_inhibited)
        elif not self.wanted and self._cookie is not None:
            self._release()

    def _on_inhibited(self, bus, res):
        self._pending = False
        try:
            self._cookie = bus.call_finish(res).unpack()[0]
        except GLib.Error as e:
            print(f"manbo: can't turn on Do Not Disturb: {e.message}")
            return
        self._update()  # state may have changed while we waited

    def _release(self):
        cookie, self._cookie = self._cookie, None
        self._call("UnInhibit", GLib.Variant("(u)", (cookie,)), None, _ignore)

    def shutdown(self):
        if self._cookie is not None:
            cookie, self._cookie = self._cookie, None
            try:
                self._bus.call_sync(NOTIFICATIONS, PATH, NOTIFICATIONS, "UnInhibit",
                                    GLib.Variant("(u)", (cookie,)), None,
                                    Gio.DBusCallFlags.NONE, TIMEOUT_MS, None)
            except GLib.Error:
                pass

    def _call(self, method, args, rtype, done):
        self._bus.call(NOTIFICATIONS, PATH, NOTIFICATIONS, method, args, rtype,
                       Gio.DBusCallFlags.NONE, TIMEOUT_MS, None, done)


def _ignore(bus, res):
    try:
        bus.call_finish(res)
    except GLib.Error:
        pass
