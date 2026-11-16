import math

from gi.repository import GLib, GObject

FOCUS, SHORT, LONG = "focus", "short", "long"
MODES = (FOCUS, SHORT, LONG)

_MINUTES_KEY = {
    FOCUS: "focus_minutes",
    SHORT: "short_break_minutes",
    LONG: "long_break_minutes",
}

TICK_MS = 100


def _wall_ms():
    return GLib.get_real_time() // 1000


class PomodoroTimer(GObject.Object):
    """Pomodoro state machine. Uses the monotonic clock so it never drifts."""

    __gsignals__ = {
        "tick": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # (finished mode, next mode)
        "finished": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self.mode = FOCUS
        self.completed = 0  # finished focus sessions
        self.running = False
        self._started = False  # has the current session been started at all?
        self._remaining_us = self._duration_us(FOCUS)
        self._end_us = 0
        self._end_wall_ms = 0  # the same end, on the wall clock (what devices sync)
        self._source = 0
        # phone sync: when and where (device id) the last user action happened;
        # the newest one wins between devices
        self.local_id = ""
        self.stamp = 0
        self.by = ""
        settings.connect("changed", self._on_settings_changed)

    # -- queries -------------------------------------------------------------

    def _duration_us(self, mode):
        return self._settings[_MINUTES_KEY[mode]] * 60 * 1_000_000

    @property
    def remaining_us(self):
        if self.running:
            return max(0, self._end_us - GLib.get_monotonic_time())
        return self._remaining_us

    @property
    def duration_seconds(self):
        """Full length of the current session."""
        return self._duration_us(self.mode) // 1_000_000

    @property
    def remaining_seconds(self):
        return math.ceil(self.remaining_us / 1_000_000)

    @property
    def cycle_position(self):
        """How many focus sessions are done in the current long-break cycle."""
        interval = self._settings["long_break_interval"]
        if self.mode == LONG:
            return interval
        return self.completed % interval

    # -- actions -------------------------------------------------------------

    def start(self):
        if self.running:
            return
        self._touch()
        self._started = True
        self._run_until(_wall_ms() + self._remaining_us // 1000)
        self.emit("changed")

    def pause(self):
        if not self.running:
            return
        self._touch()
        self._remaining_us = self.remaining_us
        self._halt()
        self.emit("changed")

    def toggle(self):
        if self.running:
            self.pause()
        else:
            self.start()

    def reset(self):
        self._touch()
        self._halt()
        self._enter(self.mode)
        self.emit("changed")

    def select(self, mode):
        """Manually switch to `mode`; stops the timer and starts that session fresh."""
        if mode == self.mode and not self._started:
            return
        self._touch()
        self._halt()
        self._enter(mode)
        self.emit("changed")

    # -- sync ----------------------------------------------------------------

    def get_state(self):
        """The timer as phone sync sends it (wall-clock times, in ms)."""
        return {
            "mode": self.mode,
            "running": self.running,
            "endAt": self._end_wall_ms if self.running else 0,
            "remainingMs": self.remaining_us // 1000,
            "started": self._started,
            "completed": self.completed,
            "stamp": self.stamp,
            "by": self.by,
        }

    def set_state(self, s):
        """Take over another device's (newer) state."""
        self._halt()
        self.mode = s["mode"]
        self.completed = s["completed"]
        self._started = s["started"]
        self.stamp, self.by = s["stamp"], s["by"]
        if s["running"]:
            self._run_until(s["endAt"])
        else:
            self._remaining_us = s["remainingMs"] * 1000
        self.emit("changed")

    def finish_now(self):
        """Another device says the running session just ended: end it here
        too (with the chime), a tick early rather than a tick late."""
        if self.running:
            self._finish()

    # -- internals -----------------------------------------------------------

    def _break_after(self, completed):
        interval = self._settings["long_break_interval"]
        return LONG if completed > 0 and completed % interval == 0 else SHORT

    def _enter(self, mode):
        self.mode = mode
        self._started = False
        self._remaining_us = self._duration_us(mode)

    def _touch(self):
        self.stamp = _wall_ms()
        self.by = self.local_id

    def _run_until(self, end_wall_ms):
        self.running = True
        self._end_wall_ms = end_wall_ms
        self._end_us = GLib.get_monotonic_time() + (end_wall_ms - _wall_ms()) * 1000
        self._source = GLib.timeout_add(TICK_MS, self._on_tick)

    def _halt(self):
        self.running = False
        if self._source:
            GLib.source_remove(self._source)
            self._source = 0

    def _on_tick(self):
        if self.remaining_us <= 0:
            self._source = 0  # returning False removes the source
            self._finish()
            return GLib.SOURCE_REMOVE
        self.emit("tick")
        return GLib.SOURCE_CONTINUE

    def _finish(self):
        # every device ends a session the same way at the same moment, so they agree
        self.stamp = self._end_wall_ms
        self._halt()
        finished = self.mode
        if finished == FOCUS:
            self.completed += 1
            nxt = self._break_after(self.completed)
        else:
            nxt = FOCUS
        self._enter(nxt)
        self.emit("finished", finished, nxt)
        self.emit("changed")

    def _on_settings_changed(self, _settings, key):
        if key in _MINUTES_KEY.values() and not self._started:
            self._remaining_us = self._duration_us(self.mode)
            self.emit("changed")
        elif key == "long_break_interval":
            self.emit("changed")
