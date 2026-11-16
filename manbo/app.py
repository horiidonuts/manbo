import sys
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import APP_ID, APP_NAME, VERSION
from .dnd import FocusDnd
from .preferences import PreferencesDialog
from .service import ManboService
from .settings import Settings
from .sounds import Sounds
from .sync import SyncServer
from .themes import build_css
from .timer import PomodoroTimer
from .window import ManboWindow


class ManboApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = None
        self.sounds = None
        self.timer = None
        self.dnd = None
        self.service = None
        self.sync = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        GLib.set_application_name(APP_NAME)
        # Pastel palettes are designed for light mode only.
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

        display = Gdk.Display.get_default()
        dev_icons = Path(__file__).resolve().parent.parent / "data" / "icons"
        if dev_icons.is_dir():  # source tree, or /usr/share/manbo/data/icons when installed
            Gtk.IconTheme.get_for_display(display).add_search_path(str(dev_icons))
        Gtk.Window.set_default_icon_name(APP_ID)

        provider = Gtk.CssProvider()
        provider.load_from_string(build_css())
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self._ensure_core()
        self.sounds = Sounds()
        self.dnd = FocusDnd(self.timer, self.settings)  # before any window: see dnd.py
        self.sync = SyncServer(self.timer, self.settings)

        for name, callback, accels in (
            ("preferences", self._on_preferences, ["<Control>comma"]),
            ("about", self._on_about, []),
            ("mini", lambda *_: self._main_window().toggle_mini(), ["<Control>m"]),
            ("quit", lambda *_: self.quit(), ["<Control>q"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def _ensure_core(self):
        """Settings + timer. Needed by both D-Bus registration and startup,
        and registration comes first."""
        if self.timer is None:
            self.settings = Settings()
            self.timer = PomodoroTimer(self.settings)

    def do_dbus_register(self, connection, object_path):
        # Export the API here, before the bus name is ours: when D-Bus
        # activation starts Manbo for a method call (e.g. from the widget),
        # that call is delivered as soon as we own the name.
        if not Adw.Application.do_dbus_register(self, connection, object_path):
            return False
        self._ensure_core()
        self.service = ManboService(
            connection, object_path, self.timer, self.settings,
            keep_alive=self._main_window,  # an (unshown) window holds the app
        )
        return True

    def do_dbus_unregister(self, connection, object_path):
        if self.service is not None:
            self.service.unregister()
            self.service = None
        Adw.Application.do_dbus_unregister(self, connection, object_path)

    def do_shutdown(self):
        if self.sync is not None:
            self.sync.shutdown()
        if self.dnd is not None:
            self.dnd.shutdown()
        if self.sounds is not None:
            self.sounds.shutdown()
        Adw.Application.do_shutdown(self)

    def do_activate(self):
        window = self._main_window()
        if window.mini_shown:
            window._mini.present()
        else:
            window.present()

    def _main_window(self):
        for window in self.get_windows():
            if isinstance(window, ManboWindow):
                return window
        return ManboWindow(self, self.settings)

    def _full_window(self):
        """The main window, back from mini mode if needed (dialogs need room)."""
        window = self._main_window()
        if window.mini_shown:
            window.leave_mini()
        return window

    def _on_preferences(self, *_):
        window = self._full_window()
        PreferencesDialog(self.settings, preview_chime=window.play_chime, sync=self.sync).present(window)

    def _on_about(self, *_):
        Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=VERSION,
            comments="A tiny pastel Pomodoro timer",
        ).present(self._full_window())


def main(argv=None):
    # No display (e.g. D-Bus activation from a session that didn't export
    # WAYLAND_DISPLAY/DISPLAY): say so and exit instead of crashing halfway.
    if not Gtk.init_check():
        print("manbo: can't open a display (is WAYLAND_DISPLAY or DISPLAY set?)", file=sys.stderr)
        return 1
    return ManboApplication().run(argv)
