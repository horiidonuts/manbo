"""Manbo speaks English and Turkish (like the phone app's Strings.kt).

Preferences → Language picks one; "system" follows LANG/LC_MESSAGES. The
texts sit right where they're used, English first: t("Pause", "Duraklat").
Widgets that are already on screen listen for the "language" setting and
set their texts again.
"""

import os

LANGUAGES = ("system", "en", "tr")

_settings = None


def init(settings):
    global _settings
    _settings = settings


def _system_turkish():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return value.split(":")[0].lower().startswith("tr")
    return False


def turkish():
    choice = _settings["language"] if _settings is not None else "system"
    if choice == "system":
        return _system_turkish()
    return choice == "tr"


def t(en, tr):
    """The text in the app's language."""
    return tr if turkish() else en


def upper(text):
    """Upper case that gets Turkish i → İ right."""
    if turkish():
        text = text.replace("i", "İ")
    return text.upper()


def lower(text):
    if turkish():
        text = text.replace("I", "ı").replace("İ", "i")
    return text.lower()
