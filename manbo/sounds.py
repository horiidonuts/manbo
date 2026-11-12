"""Sound effects.

Files live in data/sounds/. SOUNDS maps each event to a file name (without
extension, any of EXTENSIONS works) and a base volume. Missing files fall back
to the entries in FALLBACKS, or stay silent.

Playback uses one GStreamer playbin per sound that stays prerolled (PAUSED)
between plays and is rewound with a flushing seek — instant to start, no
per-play allocation, and reliable to replay any number of times.
"""

import os
from pathlib import Path

from gi.repository import GLib, Gst

Gst.init(None)

# Source tree: <repo>/data/sounds — installed: /usr/share/manbo/data/sounds
SOUND_DIR = Path(__file__).resolve().parent.parent / "data" / "sounds"
EXTENSIONS = (".ogg", ".oga", ".opus", ".wav", ".flac", ".mp3")

# event -> (file name in data/sounds without extension, base volume 0.0 .. 1.0)
SOUNDS = {
    "press": ("button_press", 1.0),   # the button sinking (start)
    "pop": ("button_pop_up", 1.0),    # the button popping up
    "chime": ("chime1", 1.0),         # a session ended
}

FALLBACKS = {
    "chime": (
        "/usr/share/sounds/freedesktop/stereo/complete.oga",
        "/usr/share/sounds/freedesktop/stereo/bell.oga",
    ),
}

# Chime length setting -> where to start playing (ms). The beginning of the
# file is skipped and it always plays to its natural end. Tuned for chime1:
# intro hits 0-0.65 s, steady tone until ~3.9 s, final hit at ~4.0 s.
CHIME_STARTS = {"short": 3950, "normal": 2000, "long": 0}
FADE_IN_MS = 120      # soften the entry when starting mid-sound
FADE_STEP_MS = 15


def _find(name, stem):
    for ext in EXTENSIONS:
        path = SOUND_DIR / f"{stem}{ext}"
        if path.is_file():
            return str(path)
    return next((p for p in FALLBACKS.get(name, ()) if os.path.exists(p)), None)


def perceptual(level):
    """0..1 slider position -> playback volume that sounds evenly spaced."""
    return max(0.0, min(1.0, level)) ** 2


class _Player:
    """One persistent, prerolled playbin for a single sound file."""

    def __init__(self, path):
        self._pipe = Gst.ElementFactory.make("playbin", None)
        self._pipe.set_property("uri", Gst.filename_to_uri(path))
        # Effects don't need clock sync. With sync on, the sink drops samples
        # it considers "late" while starting from PAUSED — that's the start of
        # the sound, so clicks came out with a softened/cut attack.
        sink = Gst.ElementFactory.make("pulsesink", None) or Gst.ElementFactory.make("autoaudiosink", None)
        if sink is not None:
            sink.set_property("sync", False)
            self._pipe.set_property("audio-sink", sink)
        self._pending_seek = None
        self._seqnum = None  # seqnum of the latest seek; older EOS messages are stale
        self._bus = self._pipe.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect("message", self._on_message)
        self._pipe.set_state(Gst.State.PAUSED)  # preroll now so play() is instant

    def play(self, start_ns, volume):
        self._pipe.set_property("volume", volume)
        if not self._seek(start_ns):
            self._pending_seek = start_ns  # not prerolled yet: seek once it is
        self._pipe.set_state(Gst.State.PLAYING)

    def set_volume(self, volume):
        self._pipe.set_property("volume", volume)

    def stop(self):
        self._pending_seek = None
        self._pipe.set_state(Gst.State.PAUSED)

    def shutdown(self):
        self._bus.remove_signal_watch()
        self._pipe.set_state(Gst.State.NULL)

    def _seek(self, start_ns):
        event = Gst.Event.new_seek(
            1.0, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
            Gst.SeekType.SET, start_ns, Gst.SeekType.NONE, -1,
        )
        self._seqnum = event.get_seqnum()
        return self._pipe.send_event(event)

    def _on_message(self, _bus, msg):
        if msg.type == Gst.MessageType.EOS:
            # Only the EOS of the latest play may pause the stream. An EOS from
            # the previous play can still be queued when a new play starts
            # (fast clicking) — pausing then would silence the new click.
            if msg.get_seqnum() == self._seqnum:
                self._pipe.set_state(Gst.State.PAUSED)
        elif msg.type == Gst.MessageType.ASYNC_DONE and self._pending_seek is not None:
            start_ns, self._pending_seek = self._pending_seek, None
            self._seek(start_ns)
        elif msg.type == Gst.MessageType.ERROR:
            # e.g. the audio server went away during suspend: rebuild the stream
            err, _debug = msg.parse_error()
            print(f"manbo: sound error, resetting player: {err.message}")
            self._pipe.set_state(Gst.State.NULL)
            self._pipe.set_state(Gst.State.PAUSED)


class _KeepAlive:
    """A silent output stream that keeps the audio device from suspending.

    PipeWire suspends an idle output after ~5 s and wireless headsets drop
    their radio link on silence; waking them up swallows the start of the
    next sound. While any reason is active this streams digital silence.
    """

    def __init__(self):
        self._pipe = Gst.parse_launch(
            "audiotestsrc wave=silence is-live=true ! audioconvert ! audioresample ! autoaudiosink"
        )
        self._reasons = set()

    def set(self, reason, active):
        was_on = bool(self._reasons)
        if active:
            self._reasons.add(reason)
        else:
            self._reasons.discard(reason)
        if bool(self._reasons) != was_on:
            self._pipe.set_state(Gst.State.PLAYING if self._reasons else Gst.State.NULL)

    def shutdown(self):
        self._reasons.clear()
        self._pipe.set_state(Gst.State.NULL)


class Sounds:
    def __init__(self):
        self._players = {}
        self._base = {}
        self._fades = {}  # name -> GLib source id of a running fade-in
        self._keepalive = _KeepAlive()
        for name, (stem, volume) in SOUNDS.items():
            path = _find(name, stem)
            if path is None:
                continue
            self._players[name] = _Player(path)
            self._base[name] = volume

    def play(self, name, level=1.0, start_ms=0):
        """Play `name` at `level` (0..1, perceptual), skipping its first
        `start_ms` milliseconds (with a short fade-in) and running to the end."""
        player = self._players.get(name)
        if player is None:
            return
        self._cancel_fade(name)
        volume = self._base[name] * perceptual(level)
        player.play(start_ms * Gst.MSECOND, 0.0 if start_ms > 0 else volume)
        if start_ms > 0:
            self._fade_in(name, player, volume)

    def stop(self, name):
        self._cancel_fade(name)
        player = self._players.get(name)
        if player is not None:
            player.stop()

    def keep_awake(self, reason, active):
        """Keep the audio device awake while `reason` is active (see _KeepAlive)."""
        self._keepalive.set(reason, active)

    def shutdown(self):
        self._keepalive.shutdown()
        for name in list(self._fades):
            self._cancel_fade(name)
        for player in self._players.values():
            player.shutdown()
        self._players.clear()

    def _cancel_fade(self, name):
        source = self._fades.pop(name, None)
        if source:
            GLib.source_remove(source)

    def _fade_in(self, name, player, volume):
        start = GLib.get_monotonic_time()

        def step():
            t = (GLib.get_monotonic_time() - start) / (FADE_IN_MS * 1000)
            if t >= 1:
                player.set_volume(volume)
                self._fades.pop(name, None)
                return GLib.SOURCE_REMOVE
            player.set_volume(volume * t)
            return GLib.SOURCE_CONTINUE

        self._fades[name] = GLib.timeout_add(FADE_STEP_MS, step)
