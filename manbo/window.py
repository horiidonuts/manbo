from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import APP_NAME
from .modewheel import ModeWheel
from .pushbutton import PushButton
from .sounds import CHIME_STARTS
from .themes import palette
from .timer import FOCUS, LONG, SHORT, PomodoroTimer

MODE_TITLES = {FOCUS: "FOCUS", SHORT: "SHORT BREAK", LONG: "LONG BREAK"}
MODE_NAMES = {FOCUS: "Focus", SHORT: "Short break", LONG: "Long break"}

# Keep the audio device awake from shortly before a session ends until the
# (longest) chime has finished, so the chime isn't cut when the window is in
# the background.
WAKE_BEFORE_END_MS = 2000
KEEP_AWAKE_AFTER_END_MS = 9000

NOTIFY_TEXT = {
    FOCUS: "Focus session done",
    SHORT: "Break is over",
    LONG: "Long break is over",
}


class ManboWindow(Adw.ApplicationWindow):
    def __init__(self, app, settings):
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(360, 640)
        self.set_size_request(300, 520)
        self.add_css_class("manbo")

        self.settings = settings
        self.timer = PomodoroTimer(settings)
        self._shown_theme = None
        self._shown_mode = None
        self.sounds = app.sounds
        self._ending_hold = 0  # GLib source that ends the post-session keep-awake

        self._build_ui()

        self.timer.connect("tick", lambda *_: self._update_time())
        self.timer.connect("changed", lambda *_: self._sync())
        self.timer.connect("finished", self._on_finished)
        # keep the audio device awake while the user can click (window focused)
        self.connect("notify::is-active", lambda *_: self.sounds.keep_awake("focus", self.is_active()))
        settings.connect("changed", self._on_settings_changed)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        self._rebuild_dots()
        self._sync(animate=False)

    # -- UI ------------------------------------------------------------------

    def _build_ui(self):
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About Manbo", "app.about")
        menu.append("Quit", "app.quit")
        self.menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic", menu_model=menu, primary=True,
            tooltip_text="Menu",
        )

        header = Adw.HeaderBar(show_title=False)
        header.add_css_class("flat")
        header.pack_end(self.menu_button)

        self.wheel = ModeWheel([(m, MODE_TITLES[m]) for m in (FOCUS, SHORT, LONG)])
        self.wheel.connect("selected", lambda _w, mode: self.timer.select(mode))
        self.time_label = Gtk.Label(css_classes=["time-label"])
        self.dots = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)

        self.button = PushButton()
        self.button.connect("activated", lambda *_: self.timer.toggle())
        self.button.connect("down-changed", self._on_button_moved)

        reset = Gtk.Button(
            icon_name="view-refresh-symbolic", tooltip_text="Reset session",
            css_classes=["flat", "circular", "round-action"], focusable=False,
        )
        reset.connect("clicked", lambda *_: self.timer.reset())
        reset.set_halign(Gtk.Align.CENTER)

        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=12,
            margin_start=24, margin_end=24, margin_top=4, margin_bottom=28,
        )
        content.append(self.wheel)
        content.append(self.time_label)
        content.append(self.dots)
        content.append(self.button)
        content.append(reset)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(content)
        self.set_content(view)

    def _rebuild_dots(self):
        while (child := self.dots.get_first_child()) is not None:
            self.dots.remove(child)
        for _ in range(self.settings["long_break_interval"]):
            self.dots.append(Gtk.Box(css_classes=["dot"], valign=Gtk.Align.CENTER))

    # -- state sync ------------------------------------------------------------

    def _sync(self, animate=True):
        mode = self.timer.mode
        theme = self.settings["theme"]
        if (theme, mode) != (self._shown_theme, self._shown_mode):
            self._apply_theme(theme, mode, animate)

        self.wheel.set_mode(mode, animate=animate)
        self._update_time()

        filled = self.timer.cycle_position
        dot = self.dots.get_first_child()
        i = 0
        while dot is not None:
            if i < filled:
                dot.add_css_class("filled")
            else:
                dot.remove_css_class("filled")
            dot = dot.get_next_sibling()
            i += 1

        self.button.set_down(self.timer.running)
        if not self.timer.running and not self._ending_hold:
            self.sounds.keep_awake("ending", False)

    def _apply_theme(self, theme, mode, animate):
        for cls in self.get_css_classes():
            if cls.startswith(("theme-", "mode-")):
                self.remove_css_class(cls)
        self.add_css_class(f"theme-{theme}")
        self.add_css_class(f"mode-{mode}")
        pal = palette(theme, mode)
        self.button.set_palette(pal["bg"], pal["button"], pal["text"], animate)
        self._shown_theme, self._shown_mode = theme, mode

    def _update_time(self):
        secs = self.timer.remaining_seconds
        text = f"{secs // 60:02d}:{secs % 60:02d}"
        if self.time_label.get_label() != text:
            self.time_label.set_label(text)
        title = f"{text} · {MODE_NAMES[self.timer.mode]}" if self.timer.running else APP_NAME
        if self.get_title() != title:
            self.set_title(title)
        if self.timer.running and self.timer.remaining_us <= WAKE_BEFORE_END_MS * 1000:
            self.sounds.keep_awake("ending", True)  # so the chime's start isn't swallowed

    # -- events ----------------------------------------------------------------

    def _on_finished(self, _timer, finished, nxt):
        self.button.set_down(False)
        self.sounds.keep_awake("ending", True)
        if self._ending_hold:
            GLib.source_remove(self._ending_hold)
        self._ending_hold = GLib.timeout_add(KEEP_AWAKE_AFTER_END_MS, self._release_ending)
        self.play_chime()
        if not self.is_active():
            note = Gio.Notification.new(NOTIFY_TEXT[finished])
            note.set_body(f"Next up: {MODE_NAMES[nxt].lower()}.")
            self.get_application().send_notification("session-finished", note)

    def _release_ending(self):
        self._ending_hold = 0
        if not self.timer.running:
            self.sounds.keep_awake("ending", False)
        return GLib.SOURCE_REMOVE

    def play_chime(self):
        length = self.settings["chime_length"]
        if length == "off":
            self.sounds.stop("chime")
            return
        self.sounds.play(
            "chime",
            level=self.settings["chime_volume"] / 100,
            start_ms=CHIME_STARTS[length],
        )

    def _on_button_moved(self, _button, down):
        if self.settings["button_sounds"]:
            self.sounds.play("press" if down else "pop")

    def _on_settings_changed(self, _settings, key):
        if key == "long_break_interval":
            self._rebuild_dots()
        self._sync()

    def _on_key(self, _ctrl, keyval, _keycode, state):
        if self.get_visible_dialog() is not None or self.menu_button.get_active():
            return False
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        if keyval in (Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.timer.toggle()
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Right):
            self.wheel.step(-1 if keyval == Gdk.KEY_Left else 1)
            return True
        return False
