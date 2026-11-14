"""Mini mode: a small always-on-top pill with the time, start/pause and a
button back to the full window. Drag it anywhere; it opens in the top-right
corner. Keeping it above other windows needs KWin (see kwin.py).
"""

from gi.repository import Gdk, GLib, Gtk

from .kwin import keep_above
from .timedisplay import TimeDisplay

TITLE = "Manbo mini"   # constant: KWin finds the window by this title
MODE_LABELS = {"focus": "FOCUS", "short": "BREAK", "long": "LONG BREAK"}
PLACE_DELAY_MS = 120   # let KWin map the window before we place it


class MiniWindow(Gtk.Window):
    def __init__(self, main):
        super().__init__(
            application=main.get_application(), title=TITLE,
            decorated=False, resizable=False,
        )
        self.add_css_class("manbo-mini")
        self._main = main
        self._timer = main.timer
        self._settings = main.settings
        self._theme_classes = []

        self._mode = Gtk.Label(css_classes=["mini-mode"], valign=Gtk.Align.CENTER)
        self._time = TimeDisplay(css_class="mini-time", fade_px=5)
        self._toggle = Gtk.Button(
            css_classes=["flat", "circular"], valign=Gtk.Align.CENTER, focusable=False,
        )
        self._toggle.connect("clicked", lambda *_: self._timer.toggle())
        expand = Gtk.Button(
            icon_name="window-maximize-symbolic", tooltip_text="Back to full window (Esc)",
            css_classes=["flat", "circular"], valign=Gtk.Align.CENTER, focusable=False,
        )
        expand.connect("clicked", lambda *_: main.leave_mini())

        pill = Gtk.Box(spacing=10, css_classes=["mini-pill"])
        pill.append(self._mode)
        pill.append(self._time)
        buttons = Gtk.Box(spacing=0)
        buttons.append(self._toggle)
        buttons.append(expand)
        pill.append(buttons)
        handle = Gtk.WindowHandle(child=pill)  # drag anywhere on the pill to move
        self.set_child(handle)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self._timer.connect("tick", lambda *_: self._update_time())
        self._timer.connect("changed", lambda *_: self._sync())
        self._settings.connect("changed", lambda *_: self._sync())
        # keep the audio device awake while the pill is focused (button clicks)
        self.connect("notify::is-active", lambda *_: main.sounds.keep_awake("mini", self.is_active()))
        self.connect("map", lambda *_: GLib.timeout_add(PLACE_DELAY_MS, self._place))
        self._sync(animate=False)

    def _place(self):
        keep_above(TITLE, True, corner=True)
        return GLib.SOURCE_REMOVE

    def _sync(self, animate=True):
        mode = self._timer.mode
        classes = [f"theme-{self._settings['theme']}", f"mode-{mode}"]
        if classes != self._theme_classes:
            for cls in self._theme_classes:
                self.remove_css_class(cls)
            for cls in classes:
                self.add_css_class(cls)
            self._theme_classes = classes
        self._mode.set_label(MODE_LABELS[mode])
        running = self._timer.running
        self._toggle.set_icon_name("media-playback-pause-symbolic" if running else "media-playback-start-symbolic")
        self._toggle.set_tooltip_text("Pause (Space)" if running else "Start (Space)")
        self._update_time(animate)

    def _update_time(self, animate=True):
        self._time.set_seconds(self._timer.remaining_seconds, animate and self._settings["clock_animations"])

    def _on_key(self, _ctrl, keyval, _keycode, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        if keyval in (Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self._timer.toggle()
            return True
        if keyval == Gdk.KEY_Escape:
            self._main.leave_mini()
            return True
        return False
