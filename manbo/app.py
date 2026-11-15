from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from . import APP_ID, APP_NAME, VERSION
from .dnd import FocusDnd
from .preferences import PreferencesDialog
from .service import ManboService
from .settings import Settings
from .sounds import Sounds
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

        self.settings = Settings()
        self.sounds = Sounds()
        self.timer = PomodoroTimer(self.settings)
        self.dnd = FocusDnd(self.timer, self.settings)  # before any window: see dnd.py
        connection = self.get_dbus_connection()
        if connection is not None:
            self.service = ManboService(connection, self.get_dbus_object_path(), self.timer)

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

    def do_shutdown(self):
        if self.dnd is not None:
            self.dnd.shutdown()
        if self.service is not None:
            self.service.unregister()
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
        PreferencesDialog(self.settings, preview_chime=window.play_chime).present(window)

    def _on_about(self, *_):
        Adw.AboutDialog(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=VERSION,
            comments="A tiny pastel Pomodoro timer",
        ).present(self._full_window())


def main(argv=None):
    return ManboApplication().run(argv)
