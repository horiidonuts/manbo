"""Focus history: every finished focus session becomes a star.

A session is stored as [end, minutes]: `end` is the wall-clock ms the session
ended at, which is the same on every synced device (they share the end time),
so it doubles as the session's id when phone and PC merge their histories.

Kept in ~/.local/share/manbo/history.json. The star layout below is mirrored
in the Android app (History.kt) so a day's constellation looks the same on
both: keep the two in step.
"""

import datetime as dt
import json
import math
import os

from gi.repository import GLib, GObject

from .timer import FOCUS


def _wall_ms():
    return GLib.get_real_time() // 1000


class History(GObject.Object):
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # sessions this device just recorded (list of [end, minutes]); sync sends them on
        "added": (GObject.SignalFlags.RUN_FIRST, None, (object,)),
    }

    def __init__(self, timer, settings):
        super().__init__()
        self._settings = settings
        self._path = os.path.join(GLib.get_user_data_dir(), "manbo", "history.json")
        self._sessions = {}   # end -> minutes
        self._load()
        timer.connect("finished", self._on_finished)
        self._timer = timer

    @property
    def sessions(self):
        """All sessions as (end, minutes), oldest first."""
        return sorted(self._sessions.items())

    def wire(self):
        return [[end, m] for end, m in self.sessions]

    def merge(self, sessions):
        """Add sessions from another device. Returns the ones that were new here."""
        new = []
        for item in sessions:
            try:
                end, minutes = int(item[0]), int(item[1])
            except (TypeError, ValueError, IndexError):
                continue
            if end > 0 and 0 < minutes <= 24 * 60 and end not in self._sessions:
                self._sessions[end] = minutes
                new.append([end, minutes])
        if new:
            self._save()
            self.emit("changed")
        return new

    def _on_finished(self, _timer, finished, _next):
        if finished != FOCUS:
            return
        end = self._timer.last_end_ms or _wall_ms()
        if end in self._sessions:
            return
        self._sessions[end] = self._settings["focus_minutes"]
        self._save()
        self.emit("changed")
        self.emit("added", [[end, self._sessions[end]]])

    # -- storage -------------------------------------------------------------------

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            for end, minutes in data.get("sessions", []):
                self._sessions[int(end)] = int(minutes)
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "sessions": self.wire()}, f, separators=(",", ":"))
            os.replace(tmp, self._path)
        except OSError as e:
            print(f"manbo: could not save history: {e}")


# -- stats ---------------------------------------------------------------------------

def local_day(end_ms):
    return dt.datetime.fromtimestamp(end_ms / 1000).date()


def week_start(day):
    return day - dt.timedelta(days=day.weekday())   # weeks start on Monday


def by_day(sessions):
    """{date: [(end, minutes), ...]} in time order."""
    days = {}
    for end, minutes in sessions:
        days.setdefault(local_day(end), []).append((end, minutes))
    return days


def streak(days, today):
    """Days in a row with at least one star, up to today (or yesterday: today isn't over)."""
    day = today if today in days else today - dt.timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= dt.timedelta(days=1)
    return n


def summary(sessions, today):
    days = by_day(sessions)
    monday = week_start(today)
    week = [days.get(monday + dt.timedelta(days=i), []) for i in range(7)]
    todays = days.get(today, [])
    return {
        "today_stars": len(todays),
        "today_minutes": sum(m for _e, m in todays),
        "week_minutes": sum(m for d in week for _e, m in d),
        "streak": streak(days, today),
        "total_stars": len(sessions),
    }


def format_minutes(minutes):
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} h {m} min"
    return f"{h} h" if h else f"{m} min"


# -- star layout (mirrored in History.kt) ---------------------------------------------
#
# Each day is a column of the week's sky. Its stars are a little random walk:
# the first lands anywhere, every next one a step away from the one before, so
# a day's sessions join up into a constellation. Positions come from a PRNG
# seeded with the date, so they never move as the day gets more stars.

COLUMN_ASPECT = 2.4        # column height / width the walk is laid out in
STEP_MIN, STEP_MAX = 0.30, 0.52
MIN_GAP = 0.24
MARGIN_X, MARGIN_Y = 0.22, 0.07
TRIES = 24


def _mulberry32(seed):
    a = seed & 0xFFFFFFFF

    def imul(x, y):
        return (x * y) & 0xFFFFFFFF

    def nxt():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = imul(a ^ (a >> 15), 1 | a)
        t = ((t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return nxt


def day_seed(day):
    return day.year * 10000 + day.month * 100 + day.day


def layout_day(day, count):
    """Positions of a day's `count` stars, as (x, y) fractions of its column."""
    rnd = _mulberry32(day_seed(day))
    lo_y, hi_y = MARGIN_Y * COLUMN_ASPECT, (1 - MARGIN_Y) * COLUMN_ASPECT
    pts = []

    def inside(x, y):
        return MARGIN_X <= x <= 1 - MARGIN_X and lo_y <= y <= hi_y

    def gap(x, y):
        return min((math.hypot(x - px, y - py) for px, py in pts), default=9.0)

    for i in range(count):
        best, best_gap = None, -1.0
        for _ in range(TRIES):
            if i == 0:
                x = MARGIN_X + rnd() * (1 - 2 * MARGIN_X)
                y = lo_y + rnd() * (hi_y - lo_y)
            else:
                angle = rnd() * 2 * math.pi
                step = STEP_MIN + rnd() * (STEP_MAX - STEP_MIN)
                x = pts[-1][0] + math.cos(angle) * step
                y = pts[-1][1] + math.sin(angle) * step
                if not inside(x, y):
                    continue
            g = gap(x, y)
            if g > best_gap:
                best, best_gap = (x, y), g
            if g >= MIN_GAP:
                break
        if best is None:   # boxed in: anywhere in the column
            best = (MARGIN_X + rnd() * (1 - 2 * MARGIN_X), lo_y + rnd() * (hi_y - lo_y))
        pts.append(best)
    return [(x, y / COLUMN_ASPECT) for x, y in pts]


def star_scale(minutes):
    """Longer sessions make bigger stars (a 25-minute one is 1)."""
    return max(0.7, min(1.6, math.sqrt(minutes / 25)))
