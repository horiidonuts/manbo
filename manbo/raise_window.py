"""Bring the window to the front from the background, without taking focus.

On Wayland an app can't raise its own window while another one is focused —
GTK's present() is silently ignored. KWin (KDE Plasma) can do it for us: we
hand it a tiny script over D-Bus that un-minimizes and raises our window.
Raising instead of activating keeps keyboard focus where the user is typing,
so a stray space/enter doesn't land in Manbo and toggle the timer.

Elsewhere (no KWin) this falls back to present(), which the compositor may
turn into an "is ready" hint instead.
"""

import os

from gi.repository import Gio, GLib

KWIN = "org.kde.KWin"
SCRIPTING_PATH = "/Scripting"
SCRIPTING_IFACE = "org.kde.kwin.Scripting"
SCRIPT_NAME = "manbo-raise"
TIMEOUT_MS = 1000

SCRIPT = """\
for (const w of workspace.windowList()) {
    if (w.pid === %d && w.normalWindow) {
        if (w.minimized) w.minimized = false;
        workspace.raiseWindow(w);
    }
}
"""


def _write_script():
    # KWin reads the file when the script runs; it's removed right after
    path = os.path.join(GLib.get_user_runtime_dir(), f"manbo-raise-{os.getpid()}.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(SCRIPT % os.getpid())
    return path


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def bring_to_front(window):
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        path = _write_script()
    except (GLib.Error, OSError) as e:
        print(f"manbo: can't raise window via KWin: {e}")
        window.present()
        return

    def call(obj_path, iface, method, args, rtype, done):
        bus.call(KWIN, obj_path, iface, method, args, rtype,
                 Gio.DBusCallFlags.NO_AUTO_START, TIMEOUT_MS, None, done)

    def unload(then):
        # a leftover script with our name (e.g. after a crash) blocks loading
        call(SCRIPTING_PATH, SCRIPTING_IFACE, "unloadScript", GLib.Variant("(s)", (SCRIPT_NAME,)),
             None, lambda b, res: (_finish(b, res), then and then()))

    def load():
        call(SCRIPTING_PATH, SCRIPTING_IFACE, "loadScript", GLib.Variant("(ss)", (path, SCRIPT_NAME)),
             GLib.VariantType("(i)"), on_loaded)

    def on_loaded(b, res):
        reply = _finish(b, res)
        if reply is None:  # not KDE / KWin not reachable
            _remove(path)
            window.present()
            return
        script_id = reply.unpack()[0]
        call(f"/Scripting/Script{script_id}", "org.kde.kwin.Script", "run", None, None,
             lambda b2, res2: (_finish(b2, res2), unload(lambda: _remove(path))))

    unload(load)


def _finish(bus, res):
    try:
        return bus.call_finish(res)
    except GLib.Error:
        return None
