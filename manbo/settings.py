import json
import os

from gi.repository import GLib, GObject

DEFAULTS = {
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_interval": 4,
    "theme": "blossom",
    "button_sounds": True,
    "chime_length": "normal",
    "chime_volume": 80,
    "raise_before_end": False,
    "clock_animations": True,
    "dnd_during_focus": False,
    "run_in_background": False,
}

# Allowed ranges for the numeric settings: (min, max)
RANGES = {
    "focus_minutes": (1, 180),
    "short_break_minutes": (1, 60),
    "long_break_minutes": (1, 120),
    "long_break_interval": (1, 12),
    "chime_volume": (0, 100),
}

# Allowed values for the choice settings
CHOICES = {
    "chime_length": ("off", "short", "normal", "long"),
}


class Settings(GObject.Object):
    """Tiny JSON-backed settings store (~/.config/manbo/settings.json)."""

    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self._path = os.path.join(GLib.get_user_config_dir(), "manbo", "settings.json")
        self._data = dict(DEFAULTS)
        self._load()

    def __getitem__(self, key):
        return self._data[key]

    def set(self, key, value):
        if key in RANGES:
            lo, hi = RANGES[key]
            value = max(lo, min(hi, int(value)))
        if key in CHOICES and value not in CHOICES[key]:
            return
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()
        self.emit("changed", key)

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                stored = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        for key, default in DEFAULTS.items():
            value = stored.get(key)
            if value is None or type(value) is not type(default):
                continue
            if key in RANGES:
                lo, hi = RANGES[key]
                value = max(lo, min(hi, value))
            if key in CHOICES and value not in CHOICES[key]:
                continue
            self._data[key] = value

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._path)
        except OSError as e:
            print(f"manbo: could not save settings: {e}")
