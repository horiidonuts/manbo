"""Small window-management helpers that Wayland doesn't let apps do themselves.

On Wayland an app can't raise its own window from the background, keep a
window above others, or place it on screen. KWin (KDE Plasma) can: we hand it
a tiny script over D-Bus that finds our window (by pid and title) and does it.
Without KWin these degrade gracefully (raising falls back to present(), the
rest is skipped).
"""

import json
import os

from gi.repository import Gio, GLib

KWIN = "org.kde.KWin"
SCRIPTING_PATH = "/Scripting"
SCRIPTING_IFACE = "org.kde.kwin.Scripting"
TIMEOUT_MS = 1000

# Every script runs this body once for each of our windows: `w`.
SCRIPT = """\
for (const w of workspace.windowList()) {
    if (w.pid !== %(pid)d || !w.normalWindow) continue;
    if (%(title)s !== null && w.caption !== %(title)s) continue;
    %(body)s
}
"""

RAISE = """
    if (w.minimized) w.minimized = false;
    workspace.raiseWindow(w);
"""

# Keep above others, optionally move into the top-right corner of the work
# area of the screen the pointer is on.
KEEP_ABOVE = """
    w.keepAbove = %(above)s;
    w.skipTaskbar = %(above)s;
    if (%(corner)s) {
        const area = workspace.clientArea(KWin.PlacementArea, workspace.activeScreen, workspace.currentDesktop);
        const g = w.frameGeometry;
        w.frameGeometry = {x: area.x + area.width - g.width - %(margin)d,
                           y: area.y + %(margin)d, width: g.width, height: g.height};
    }
    workspace.raiseWindow(w);
"""

_counter = 0


def run_script(body, title=None, on_done=None):
    """Run `body` in KWin for each of our windows (only the one titled `title`
    if given). `on_done(ok)` is called once it ran, or failed (no KWin)."""
    global _counter
    _counter += 1
    name = f"manbo-{os.getpid()}-{_counter}"
    source = SCRIPT % {"pid": os.getpid(), "title": json.dumps(title), "body": body}
    # KWin reads the file when the script runs; it's removed right after
    path = os.path.join(GLib.get_user_runtime_dir(), f"{name}.js")
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        with open(path, "w", encoding="utf-8") as f:
            f.write(source)
    except (GLib.Error, OSError) as e:
        print(f"manbo: can't talk to KWin: {e}")
        if on_done:
            on_done(False)
        return

    def call(obj_path, iface, method, args, rtype, done):
        bus.call(KWIN, obj_path, iface, method, args, rtype,
                 Gio.DBusCallFlags.NO_AUTO_START, TIMEOUT_MS, None, done)

    def finish(ok):
        try:
            os.remove(path)
        except OSError:
            pass
        if on_done:
            on_done(ok)

    def on_loaded(b, res):
        reply = _finish(b, res)
        if reply is None:  # not KDE / KWin not reachable
            finish(False)
            return
        script_id = reply.unpack()[0]
        call(f"/Scripting/Script{script_id}", "org.kde.kwin.Script", "run", None, None, on_ran)

    def on_ran(b, res):
        ok = _finish(b, res) is not None
        call(SCRIPTING_PATH, SCRIPTING_IFACE, "unloadScript", GLib.Variant("(s)", (name,)),
             None, lambda b2, res2: (_finish(b2, res2), finish(ok)))

    call(SCRIPTING_PATH, SCRIPTING_IFACE, "loadScript", GLib.Variant("(ss)", (path, name)),
         GLib.VariantType("(i)"), on_loaded)


def bring_to_front(window):
    """Raise `window` (and un-minimize it) without taking keyboard focus, so
    a stray space/enter typed elsewhere doesn't land in Manbo."""
    run_script(RAISE, on_done=lambda ok: ok or window.present())


def keep_above(title, above, corner=False, margin=16):
    """Keep our window titled `title` above all others (and out of the task
    bar); with `corner`, also move it to the top-right corner."""
    js = "true" if above else "false"
    run_script(KEEP_ABOVE % {"above": js, "corner": "true" if corner else "false", "margin": margin},
               title=title)


def _finish(bus, res):
    try:
        return bus.call_finish(res)
    except GLib.Error:
        return None
