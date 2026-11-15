from gi.repository import Adw, GLib, Gtk

from .settings import CHOICES, RANGES
from .themes import THEMES

CHIME_LENGTH_NAMES = {"off": "Off", "short": "Short", "normal": "Normal", "long": "Long"}
PREVIEW_DELAY_MS = 350  # wait for the slider to settle before previewing


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings, preview_chime=None):
        super().__init__(title="Preferences")
        self._settings = settings
        self._preview_chime = preview_chime
        self._preview_source = 0
        self.connect("closed", self._on_closed)

        page = Adw.PreferencesPage()
        self.add(page)

        # -- timer -----------------------------------------------------------
        timer = Adw.PreferencesGroup(title="Timer")
        page.add(timer)
        timer.add(self._spin("Focus", "Minutes", "focus_minutes"))
        timer.add(self._spin("Short break", "Minutes", "short_break_minutes"))
        timer.add(self._spin("Long break", "Minutes", "long_break_minutes"))
        timer.add(self._spin(
            "Long break interval", "Focus sessions before a long break",
            "long_break_interval",
        ))

        # -- focus -----------------------------------------------------------
        focus = Adw.PreferencesGroup(title="Focus")
        page.add(focus)
        focus.add(self._switch(
            "Do Not Disturb while focusing",
            "Silence other notifications while a focus session runs",
            "dnd_during_focus",
        ))

        # -- window ----------------------------------------------------------
        window = Adw.PreferencesGroup(title="Window")
        page.add(window)
        window.add(self._switch(
            "Keep running when closed",
            "The timer keeps going in the background; open Manbo again to bring it back",
            "run_in_background",
        ))
        raise_row = Adw.SwitchRow(
            title="Show window before time is up",
            subtitle="Bring Manbo to the front a second before a session ends",
        )
        raise_row.set_active(settings["raise_before_end"])
        raise_row.connect("notify::active", lambda row, _p: settings.set("raise_before_end", row.get_active()))
        window.add(raise_row)

        # -- appearance ------------------------------------------------------
        look = Adw.PreferencesGroup(title="Appearance")
        page.add(look)
        themes = list(THEMES)
        look.add(self._combo(
            "Theme", "theme", themes, [THEMES[k]["name"] for k in themes],
        ))
        roll = Adw.SwitchRow(
            title="Rolling digits",
            subtitle="Digits roll as time passes and when the timer resets",
        )
        roll.set_active(settings["clock_animations"])
        roll.connect("notify::active", lambda row, _p: settings.set("clock_animations", row.get_active()))
        look.add(roll)

        # -- sound -----------------------------------------------------------
        sound = Adw.PreferencesGroup(title="Sound")
        page.add(sound)

        clicks = Adw.SwitchRow(title="Button sounds", subtitle="Clicks for the button and when switching modes")
        clicks.set_active(settings["button_sounds"])
        clicks.connect("notify::active", lambda row, _p: settings.set("button_sounds", row.get_active()))
        sound.add(clicks)

        lengths = list(CHOICES["chime_length"])
        sound.add(self._combo(
            "Chime", "chime_length", lengths, [CHIME_LENGTH_NAMES[k] for k in lengths],
            subtitle="Plays when a session ends", preview=True,
        ))

        self._volume_row = Adw.ActionRow(title="Chime volume")
        lo, hi = RANGES["chime_volume"]
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        scale.set_value(settings["chime_volume"])
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.CENTER)
        scale.set_size_request(150, -1)
        percent = Gtk.Label(width_chars=4, xalign=1, css_classes=["dim-label", "numeric"])
        percent.set_label(f"{settings['chime_volume']}%")

        def on_volume(s):
            value = int(round(s.get_value()))
            percent.set_label(f"{value}%")
            settings.set("chime_volume", value)
            self._schedule_preview()

        scale.connect("value-changed", on_volume)
        self._volume_row.add_suffix(scale)
        self._volume_row.add_suffix(percent)
        sound.add(self._volume_row)

        self._settings_handler = settings.connect("changed", self._on_settings_changed)
        self._update_sensitivity()

    # -- helpers ---------------------------------------------------------------

    def _switch(self, title, subtitle, key):
        row = Adw.SwitchRow(title=title, subtitle=subtitle)
        row.set_active(self._settings[key])
        row.connect("notify::active", lambda r, _p: self._settings.set(key, r.get_active()))
        return row

    def _spin(self, title, subtitle, key):
        lo, hi = RANGES[key]
        row = Adw.SpinRow.new_with_range(lo, hi, 1)
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.set_value(self._settings[key])
        row.connect("notify::value", lambda r, _p: self._settings.set(key, int(r.get_value())))
        return row

    def _combo(self, title, key, values, names, subtitle=None, preview=False):
        row = Adw.ComboRow(title=title, model=Gtk.StringList.new(names))
        if subtitle:
            row.set_subtitle(subtitle)
        current = self._settings[key]
        row.set_selected(values.index(current) if current in values else 0)

        def on_selected(r, _p):
            self._settings.set(key, values[r.get_selected()])
            if preview:
                self._schedule_preview()

        row.connect("notify::selected", on_selected)
        return row

    def _on_closed(self, *_):
        self._cancel_preview()
        self._settings.disconnect(self._settings_handler)

    def _on_settings_changed(self, _settings, key):
        if key == "chime_length":
            self._update_sensitivity()

    def _update_sensitivity(self):
        self._volume_row.set_sensitive(self._settings["chime_length"] != "off")

    def _schedule_preview(self):
        if self._preview_chime is None:
            return
        self._cancel_preview()
        self._preview_source = GLib.timeout_add(PREVIEW_DELAY_MS, self._run_preview)

    def _run_preview(self):
        self._preview_source = 0
        self._preview_chime()
        return GLib.SOURCE_REMOVE

    def _cancel_preview(self):
        if self._preview_source:
            GLib.source_remove(self._preview_source)
            self._preview_source = 0
