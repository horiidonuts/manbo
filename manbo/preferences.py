from gi.repository import Adw, GLib, Gtk

from .i18n import LANGUAGES, t, turkish
from .pairing import PairDialog
from .settings import CHOICES, RANGES
from .themes import THEMES

PREVIEW_DELAY_MS = 350  # wait for the slider to settle before previewing


def _chime_names():
    return {"off": t("Off", "Kapalı"), "short": t("Short", "Kısa"),
            "normal": t("Normal", "Normal"), "long": t("Long", "Uzun")}


def _language_names():
    # each language in its own words, "system" in the current one
    return {"system": t("System", "Sistem"), "en": "English", "tr": "Türkçe"}


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings, preview_chime=None, sync=None):
        super().__init__()
        self._settings = settings
        self._sync = sync
        self._preview_chime = preview_chime
        self._preview_source = 0
        self._page = None
        self.connect("closed", self._on_closed)
        self._settings_handler = settings.connect("changed", self._on_settings_changed)
        if sync is not None:
            self._peers_handler = sync.connect("peers-changed", lambda *_: self._update_phone())
        self._build()

    def _build(self):
        """All the rows, in the current language (again when it changes)."""
        settings = self._settings
        sync = self._sync
        self.set_title(t("Preferences", "Tercihler"))
        if self._page is not None:
            self.remove(self._page)
        page = self._page = Adw.PreferencesPage()
        self.add(page)

        # -- timer -----------------------------------------------------------
        timer = Adw.PreferencesGroup(title=t("Timer", "Zamanlayıcı"))
        page.add(timer)
        minutes = t("Minutes", "Dakika")
        timer.add(self._spin(t("Focus", "Odak"), minutes, "focus_minutes"))
        timer.add(self._spin(t("Short break", "Kısa mola"), minutes, "short_break_minutes"))
        timer.add(self._spin(t("Long break", "Uzun mola"), minutes, "long_break_minutes"))
        timer.add(self._spin(
            t("Long break interval", "Uzun mola aralığı"),
            t("Focus sessions before a long break", "Uzun moladan önceki odak seansı sayısı"),
            "long_break_interval",
        ))

        # -- focus -----------------------------------------------------------
        focus = Adw.PreferencesGroup(title=t("Focus", "Odak"))
        page.add(focus)
        focus.add(self._switch(
            t("Do Not Disturb while focusing", "Odaklanırken Rahatsız Etmeyin"),
            t("Silence other notifications while a focus session runs",
              "Odak seansı sürerken diğer bildirimleri sustur"),
            "dnd_during_focus",
        ))

        # -- phone -----------------------------------------------------------
        if sync is not None:
            phone = Adw.PreferencesGroup(
                title=t("Phone", "Telefon"),
                description=t("Keep Manbo on your Android phone in step: start, pause or skip on "
                              "either one. Timer lengths are shared too.",
                              "Android telefonundaki Manbo ile birlikte çalışsın: ikisinden birinde başlat, "
                              "duraklat ya da atla. Süreler de paylaşılır."),
            )
            page.add(phone)
            self._phone_row = Adw.ActionRow(title=t("Pair a phone", "Telefon eşleştir"))
            pair = Gtk.Button(label=t("Show code", "Kodu göster"), valign=Gtk.Align.CENTER)
            pair.connect("clicked", lambda *_: PairDialog(sync).present(self))
            self._phone_row.add_suffix(pair)
            phone.add(self._phone_row)
            self._forget_row = Adw.ActionRow(
                title=t("Forget paired phones", "Eşleşmiş telefonları unut"),
                subtitle=t("They stop syncing until you pair them again",
                           "Yeniden eşleştirene kadar senkron durur"),
            )
            forget = Gtk.Button(label=t("Forget", "Unut"), valign=Gtk.Align.CENTER,
                                css_classes=["destructive-action"])
            forget.connect("clicked", self._on_forget)
            self._forget_row.add_suffix(forget)
            phone.add(self._forget_row)
            self._update_phone()

        # -- window ----------------------------------------------------------
        window = Adw.PreferencesGroup(title=t("Window", "Pencere"))
        page.add(window)
        window.add(self._switch(
            t("Keep running when closed", "Kapatınca çalışmaya devam et"),
            t("The timer keeps going in the background; open Manbo again to bring it back",
              "Zamanlayıcı arka planda sürer; geri getirmek için Manbo'yu tekrar aç"),
            "run_in_background",
        ))
        window.add(self._switch(
            t("Show window before time is up", "Süre dolmadan pencereyi göster"),
            t("Bring Manbo to the front a second before a session ends",
              "Seans bitmeden bir saniye önce Manbo'yu öne getir"),
            "raise_before_end",
        ))

        # -- appearance ------------------------------------------------------
        look = Adw.PreferencesGroup(title=t("Appearance", "Görünüm"))
        page.add(look)
        themes = list(THEMES)
        name_key = "name_tr" if turkish() else "name"
        look.add(self._combo(
            t("Theme", "Tema"), "theme", themes, [THEMES[k][name_key] for k in themes],
        ))
        look.add(self._switch(
            t("Rolling digits", "Kayan rakamlar"),
            t("Digits roll as time passes and when the timer resets",
              "Rakamlar zaman geçtikçe ve zamanlayıcı sıfırlanınca kayar"),
            "clock_animations",
        ))

        # -- sound -----------------------------------------------------------
        sound = Adw.PreferencesGroup(title=t("Sound", "Ses"))
        page.add(sound)
        sound.add(self._switch(
            t("Button sounds", "Buton sesleri"),
            t("Clicks for the button and when switching modes", "Butona basınca ve mod değiştirince tık sesi"),
            "button_sounds",
        ))

        lengths = list(CHOICES["chime_length"])
        names = _chime_names()
        sound.add(self._combo(
            t("Chime", "Zil"), "chime_length", lengths, [names[k] for k in lengths],
            subtitle=t("Plays when a session ends", "Seans bitince çalar"), preview=True,
        ))

        self._volume_row = Adw.ActionRow(title=t("Chime volume", "Zil sesi"))
        lo, hi = RANGES["chime_volume"]
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        scale.set_value(settings["chime_volume"])
        scale.set_draw_value(False)
        scale.set_hexpand(True)
        scale.set_valign(Gtk.Align.CENTER)
        scale.set_size_request(150, -1)
        percent = Gtk.Label(width_chars=4, xalign=1, css_classes=["dim-label", "numeric"])

        def show_percent(value):
            percent.set_label(f"%{value}" if turkish() else f"{value}%")

        show_percent(settings["chime_volume"])

        def on_volume(s):
            value = int(round(s.get_value()))
            show_percent(value)
            settings.set("chime_volume", value)
            self._schedule_preview()

        scale.connect("value-changed", on_volume)
        self._volume_row.add_suffix(scale)
        self._volume_row.add_suffix(percent)
        sound.add(self._volume_row)
        self._update_sensitivity()

        # -- language --------------------------------------------------------
        language = Adw.PreferencesGroup()
        page.add(language)
        names = _language_names()
        language.add(self._combo(
            t("Language", "Dil"), "language", list(LANGUAGES), [names[k] for k in LANGUAGES],
        ))

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
        if self._sync is not None:
            self._sync.disconnect(self._peers_handler)

    def _update_phone(self):
        phones = self._sync.phones
        if phones:
            subtitle = t("Connected: {}", "Bağlı: {}").format(", ".join(phones))
        elif self._sync.paired:
            subtitle = t("Paired, phone not connected right now", "Eşleşmiş, telefon şu an bağlı değil")
        else:
            subtitle = t("Scan a code with the Manbo app", "Manbo uygulamasıyla kodu tara")
        self._phone_row.set_subtitle(subtitle)
        self._forget_row.set_visible(self._sync.paired)

    def _on_forget(self, *_):
        self._sync.forget()
        self._update_phone()

    def _on_settings_changed(self, _settings, key):
        if key == "chime_length":
            self._update_sensitivity()
        elif key == "language":
            # after the combo's own signal is done: it's one of the rows being replaced
            GLib.idle_add(self._rebuild_for_language)

    def _rebuild_for_language(self):
        self._build()
        # the language row is at the bottom, where the user just was
        GLib.idle_add(self._scroll_to_end)
        return GLib.SOURCE_REMOVE

    def _scroll_to_end(self):
        child = self._page
        while child is not None and not isinstance(child, Gtk.ScrolledWindow):
            child = child.get_first_child()
        if child is not None:
            adj = child.get_vadjustment()
            adj.set_value(adj.get_upper())
        return GLib.SOURCE_REMOVE

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
