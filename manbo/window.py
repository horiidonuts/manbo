from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import APP_NAME
from .modewheel import ModeWheel
from .pushbutton import PushButton
from .kwin import bring_to_front
from .mini import MiniWindow
from .timedisplay import TimeDisplay
from .sounds import CHIME_STARTS
from .themes import palette
from .timer import FOCUS, LONG, SHORT

MODE_TITLES = {FOCUS: "FOCUS", SHORT: "SHORT BREAK", LONG: "LONG BREAK"}
MODE_NAMES = {FOCUS: "Focus", SHORT: "Short break", LONG: "Long break"}

# Keep the audio device awake from shortly before a session ends until the
# (longest) chime has finished, so the chime isn't cut when the window is in
# the background.
WAKE_BEFORE_END_MS = 2000
KEEP_AWAKE_AFTER_END_MS = 9000
# "Show window before time is up": bring the window to the front this long
# before a session ends
RAISE_BEFORE_END_MS = 1000
# When a session ends the button pops first; this long after, the wheel,
# colors and clock move on to the next session (so it reads as two beats).
HANDOFF_MS = 500

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
        self.timer = app.timer
        self._shown_theme = None
        self._shown_mode = None
        self.sounds = app.sounds
        self._ending_hold = 0  # GLib source that ends the post-session keep-awake
        self._raised = False  # already brought to front for the current ending
        self._mini = None     # MiniWindow, created on first use
        self._handoff = 0     # GLib source: still showing the finished session at 00:00
        self._handoff_mode = None

        self._build_ui()

        self.timer.connect("tick", lambda *_: self._update_time())
        self.timer.connect("changed", lambda *_: self._sync())
        self.timer.connect("finished", self._on_finished)
        # keep the audio device awake while the user can click (window focused)
        self.connect("notify::is-active", self._on_active_changed)
        settings.connect("changed", self._on_settings_changed)
        self.connect("close-request", self._on_close_request)

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

        mini = Gtk.Button(
            icon_name="manbo-mini-symbolic", tooltip_text="Mini mode (Ctrl+M)",
            action_name="app.mini",
        )

        stars = Gtk.Button(
            icon_name="manbo-stars-symbolic", tooltip_text="Your stars (Ctrl+S)",
            action_name="app.stars",
        )

        header = Adw.HeaderBar(show_title=False)
        header.add_css_class("flat")
        header.pack_end(self.menu_button)
        header.pack_end(stars)
        header.pack_start(mini)

        self.wheel = ModeWheel([(m, MODE_TITLES[m]) for m in (FOCUS, SHORT, LONG)])
        self.wheel.connect("selected", self._on_mode_selected)
        self.time_label = TimeDisplay()
        self.dots = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)

        self.button = PushButton()
        self.button.connect("activated", lambda *_: self.timer.toggle())
        self.button.connect("down-changed", self._on_button_moved)

        reset = Gtk.Button(
            icon_name="view-refresh-symbolic", tooltip_text="Reset session",
            css_classes=["flat", "circular", "round-action"], focusable=False,
        )
        reset.connect("clicked", lambda *_: (self._cancel_handoff(), self.timer.reset()))
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

    # What the UI shows. Right after a session ends that's still the finished
    # session at 00:00 for HANDOFF_MS, then the next one.
    @property
    def display_mode(self):
        return self._handoff_mode or self.timer.mode

    @property
    def display_seconds(self):
        return 0 if self._handoff_mode else self.timer.remaining_seconds

    def _start_handoff(self, finished):
        self._cancel_handoff()
        self._handoff_mode = finished
        self._handoff = GLib.timeout_add(HANDOFF_MS, self._end_handoff)

    def _end_handoff(self):
        self._handoff = 0
        self._handoff_mode = None
        self._sync()
        if self._mini is not None:
            self._mini.sync()
        return GLib.SOURCE_REMOVE

    def _cancel_handoff(self):
        """The user acted (start, switch, reset) — show the real state now."""
        if self._handoff:
            GLib.source_remove(self._handoff)
            self._end_handoff()

    def _sync(self, animate=True):
        if self._handoff and self.timer.running:  # started again within the handoff
            self._cancel_handoff()
            return
        mode = self.display_mode
        theme = self.settings["theme"]
        if (theme, mode) != (self._shown_theme, self._shown_mode):
            self._apply_theme(theme, mode, animate)

        self.wheel.set_mode(mode, animate=animate)
        self._update_time(animate)

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

    def _update_time(self, animate=True):
        secs = self.display_seconds
        self.time_label.set_seconds(secs, animate and self.settings["clock_animations"])
        text = self.time_label.text
        title = f"{text} · {MODE_NAMES[self.display_mode]}" if self.timer.running else APP_NAME
        if self.get_title() != title:
            self.set_title(title)
        if self.timer.running and self.timer.remaining_us <= WAKE_BEFORE_END_MS * 1000:
            self.sounds.keep_awake("ending", True)  # so the chime's start isn't swallowed
        self._maybe_raise()

    def _on_close_request(self, *_):
        if not self.settings["run_in_background"]:
            return False  # close -> the app quits
        # hide instead: the timer, D-Bus API and Do Not Disturb keep going;
        # launching Manbo again brings the window back
        self.set_visible(False)
        return True

    # -- mini mode -------------------------------------------------------------

    @property
    def mini_shown(self):
        return self._mini is not None and self._mini.get_visible()

    def enter_mini(self):
        if self._mini is None:
            self._mini = MiniWindow(self)
        self._mini.present()
        self.set_visible(False)

    def leave_mini(self):
        self.present()
        if self._mini is not None:
            self._mini.set_visible(False)

    def toggle_mini(self):
        if self.mini_shown:
            self.leave_mini()
        else:
            self.enter_mini()

    def _maybe_raise(self):
        if not self.timer.running or self.timer.remaining_us > RAISE_BEFORE_END_MS * 1000:
            self._raised = False
            return
        if self._raised or not self.settings["raise_before_end"] or self.is_active() or self.mini_shown:
            return
        self._raised = True
        bring_to_front(self)

    # -- events ----------------------------------------------------------------

    def _on_finished(self, _timer, finished, nxt):
        self._start_handoff(finished)  # before the timer's "changed" re-syncs the UI
        self.button.set_down(False)
        self.sounds.keep_awake("ending", True)
        if self._ending_hold:
            GLib.source_remove(self._ending_hold)
        self._ending_hold = GLib.timeout_add(KEEP_AWAKE_AFTER_END_MS, self._release_ending)
        self.play_chime()
        if not self.is_active() and not self.mini_shown:  # the always-on-top pill shows it already
            note = Gio.Notification.new(NOTIFY_TEXT[finished])
            note.set_body(f"Next up: {MODE_NAMES[nxt].lower()}.")
            # Urgent = "critical" urgency, which Do Not Disturb lets through
            # (KDE: on by default; GNOME shows urgent ones too). The user turns
            # DND on to focus — the end-of-session alert must still arrive.
            note.set_priority(Gio.NotificationPriority.URGENT)
            self.get_application().send_notification("session-finished", note)

    def _on_active_changed(self, *_):
        active = self.is_active()
        self.sounds.keep_awake("focus", active)
        if active:
            # critical notifications don't time out; clear it once the user is back
            self.get_application().withdraw_notification("session-finished")

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

    def _on_mode_selected(self, _wheel, mode):
        # only manual switches land here; the automatic one after a session
        # moves the wheel without emitting "selected"
        if self.settings["button_sounds"]:
            self.sounds.play("tab")
        self._cancel_handoff()
        self.timer.select(mode)

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
