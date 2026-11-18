"""The stars dialog: a week of night sky, one constellation per day, and stats."""

import datetime as dt
import math

import cairo

from gi.repository import Adw, Gtk

from .history import (
    by_day, format_minutes, layout_day, star_scale, summary, week_start, _mulberry32,
)
from .themes import WHITE, hex_to_rgb, mix, palette

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
BLACK = (0.0, 0.0, 0.0)
STAR_R = 8.5           # radius of a 25-minute star, px
LABEL_BAND = 40        # room for the day names under the sky
SKY_HEIGHT = 280

# The logo's four-pointed star, one quarter of it (top tip -> right tip), radius 1.
_QUARTER = ((0.0, -1.0, 0.1799, -0.5272, 0.3536, -0.3534),
            (0.5273, -0.1797, 1.0, 0.0, 1.0, 0.0))


def star_path(cr, cx, cy, r):
    cr.move_to(cx, cy - r)
    for q in range(4):   # rotate the quarter by 90° four times
        c, s = math.cos(q * math.pi / 2), math.sin(q * math.pi / 2)
        for seg in _QUARTER:
            pts = []
            for i in range(0, 6, 2):
                x, y = seg[i], seg[i + 1]
                pts += [cx + (x * c - y * s) * r, cy + (x * s + y * c) * r]
            cr.curve_to(*pts)
    cr.close_path()


def sky_colors(theme):
    pal = palette(theme, "focus")
    text, bg = hex_to_rgb(pal["text"]), hex_to_rgb(pal["bg"])
    button = hex_to_rgb(pal["button"])
    return {   # night up top, a little of the theme's dusk down at the horizon
        "top": mix(text, BLACK, 0.6),
        "bottom": mix(mix(text, button, 0.35), BLACK, 0.3),
        "star": mix(bg, WHITE, 0.55),
        "accent": hex_to_rgb(pal["button"]),
    }


class SkyView(Gtk.DrawingArea):
    """One week of sky. `days` is {date: [(end, minutes), ..]}."""

    def __init__(self):
        super().__init__(content_height=SKY_HEIGHT, hexpand=True, has_tooltip=True)
        self.monday = week_start(dt.date.today())
        self.days = {}
        self.theme = "blossom"
        self._stars = []   # (x, y, end, minutes) as last drawn, for tooltips
        self.set_draw_func(self._draw)
        self.connect("query-tooltip", self._on_tooltip)

    def show(self, monday, days, theme):
        self.monday, self.days, self.theme = monday, days, theme
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        colors = sky_colors(self.theme)
        today = dt.date.today()

        # the sky, a rounded card
        radius = 18
        cr.new_sub_path()
        cr.arc(w - radius, radius, radius, -math.pi / 2, 0)
        cr.arc(w - radius, h - radius, radius, 0, math.pi / 2)
        cr.arc(radius, h - radius, radius, math.pi / 2, math.pi)
        cr.arc(radius, radius, radius, math.pi, 3 * math.pi / 2)
        cr.close_path()
        grad = cairo.LinearGradient(0, 0, 0, h)
        grad.add_color_stop_rgb(0, *colors["top"])
        grad.add_color_stop_rgb(1, *colors["bottom"])
        cr.set_source(grad)
        cr.fill_preserve()
        cr.clip()

        # faint stardust, the same every time this week is shown
        rnd = _mulberry32(self.monday.toordinal())
        for _ in range(int(w * h / 1400)):
            x, y, size, alpha = rnd() * w, rnd() * h, 0.5 + rnd() * 0.8, 0.15 + rnd() * 0.3
            cr.set_source_rgba(*colors["star"], alpha)
            cr.arc(x, y, size, 0, 2 * math.pi)
            cr.fill()

        col_w = w / 7
        star_r = min(STAR_R, col_w * 0.1)   # a narrow sky gets smaller stars
        sky_h = h - LABEL_BAND
        self._stars = []
        any_stars = False
        for i in range(7):
            day = self.monday + dt.timedelta(days=i)
            sessions = self.days.get(day, [])
            x0 = i * col_w

            # today: a soft glow behind its column
            if day == today:
                glow = cairo.LinearGradient(0, 0, 0, h)
                glow.add_color_stop_rgba(0, *colors["star"], 0.0)
                glow.add_color_stop_rgba(1, *colors["star"], 0.10)
                cr.set_source(glow)
                cr.rectangle(x0 + 4, 0, col_w - 8, h)
                cr.fill()

            # day name
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD if day == today else cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            alpha = 0.95 if day == today else (0.35 if day > today else 0.6)
            cr.set_source_rgba(*colors["star"], alpha)
            for text, dy in ((DAY_NAMES[i], 17), (str(day.day), 31)):
                ext = cr.text_extents(text)
                cr.move_to(x0 + col_w / 2 - ext.x_advance / 2, sky_h + dy)
                cr.show_text(text)

            if not sessions:
                continue
            any_stars = True
            pts = [(x0 + px * col_w, 6 + py * (sky_h - 12))
                   for px, py in layout_day(day, len(sessions))]

            # the constellation's lines, in the order the stars were earned
            cr.set_source_rgba(*colors["star"], 0.32)
            cr.set_line_width(1.2)
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                cr.move_to(ax, ay)
                cr.line_to(bx, by)
                cr.stroke()

            for (x, y), (end, minutes) in zip(pts, sessions):
                r = star_r * star_scale(minutes)
                halo = cairo.RadialGradient(x, y, 0, x, y, r * 2.4)
                halo.add_color_stop_rgba(0, *colors["star"], 0.34)
                halo.add_color_stop_rgba(1, *colors["star"], 0.0)
                cr.set_source(halo)
                cr.arc(x, y, r * 2.4, 0, 2 * math.pi)
                cr.fill()
                cr.set_source_rgb(*colors["star"])
                star_path(cr, x, y, r)
                cr.fill()
                self._stars.append((x, y, end, minutes))

        if not any_stars:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(13)
            cr.set_source_rgba(*colors["star"], 0.75)
            text = ("Finish a focus session to light your first star"
                    if self.monday == week_start(today) else "No stars this week")
            ext = cr.text_extents(text)
            cr.move_to(w / 2 - ext.x_advance / 2, sky_h / 2)
            cr.show_text(text)

    def _on_tooltip(self, _area, x, y, _keyboard, tooltip):
        best = min(self._stars, key=lambda s: math.hypot(s[0] - x, s[1] - y), default=None)
        if best is None or math.hypot(best[0] - x, best[1] - y) > 16:
            return False
        when = dt.datetime.fromtimestamp(best[2] / 1000)
        tooltip.set_text(f"{DAY_NAMES[when.weekday()]} {when:%H:%M} · {format_minutes(best[3])}")
        return True


class _Stat(Gtk.Box):
    def __init__(self, caption):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                         css_classes=["card", "stars-stat"], hexpand=True)
        self.value = Gtk.Label(css_classes=["title-2"], xalign=0)
        self.caption = Gtk.Label(label=caption, css_classes=["dim-label", "caption"], xalign=0,
                                 wrap=True)
        self.append(self.value)
        self.append(self.caption)


class StarsDialog(Adw.Dialog):
    def __init__(self, history, settings):
        super().__init__(title="Your stars", content_width=600, content_height=600)
        self._history = history
        self._settings = settings
        self._offset = 0   # weeks back from this one

        self.sky = SkyView()
        self._prev = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text="Previous week",
                                css_classes=["flat", "circular"])
        self._next = Gtk.Button(icon_name="go-next-symbolic", tooltip_text="Next week",
                                css_classes=["flat", "circular"])
        self._prev.connect("clicked", lambda *_: self._move(1))
        self._next.connect("clicked", lambda *_: self._move(-1))
        self._week_label = Gtk.Label(css_classes=["heading"], hexpand=True)
        nav = Gtk.Box(spacing=6)
        nav.append(self._prev)
        nav.append(self._week_label)
        nav.append(self._next)

        self._today = _Stat("today")
        self._streak = _Stat("days in a row")
        self._week = _Stat("this week")
        self._total = _Stat("stars in all")
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, column_homogeneous=True)
        grid.attach(self._today, 0, 0, 1, 1)
        grid.attach(self._streak, 1, 0, 1, 1)
        grid.attach(self._week, 0, 1, 1, 1)
        grid.attach(self._total, 1, 1, 1, 1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14,
                      margin_start=18, margin_end=18, margin_top=6, margin_bottom=18)
        box.append(nav)
        box.append(self.sky)
        box.append(grid)

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        scroll.set_child(box)
        view.set_content(scroll)
        self.set_child(view)

        handlers = [(history, history.connect("changed", lambda *_: self._refresh())),
                    (settings, settings.connect("changed", self._on_setting))]
        self.connect("closed", lambda *_: [obj.disconnect(h) for obj, h in handlers])
        self._refresh()

    def _on_setting(self, _settings, key):
        if key == "theme":
            self._refresh()

    def _move(self, weeks):
        self._offset = max(0, self._offset + weeks)
        self._refresh()

    def _refresh(self):
        sessions = self._history.sessions
        today = dt.date.today()
        days = by_day(sessions)
        this_monday = week_start(today)
        monday = this_monday - dt.timedelta(weeks=self._offset)
        first = week_start(min(days)) if days else this_monday
        self._prev.set_sensitive(monday > first)
        self._next.set_sensitive(self._offset > 0)

        if self._offset == 0:
            self._week_label.set_label("This week")
        elif self._offset == 1:
            self._week_label.set_label("Last week")
        else:
            sunday = monday + dt.timedelta(days=6)
            self._week_label.set_label(f"{monday:%b} {monday.day} – {sunday:%b} {sunday.day}")
        self.sky.show(monday, days, self._settings["theme"])

        s = summary(sessions, today)
        week_minutes = sum(m for i in range(7) for _e, m in days.get(monday + dt.timedelta(days=i), []))
        stars = s["today_stars"]
        self._today.value.set_label(f"{stars} {'star' if stars == 1 else 'stars'}")
        self._today.caption.set_label(f"today · {format_minutes(s['today_minutes'])}" if stars else "today")
        self._streak.value.set_label(str(s["streak"]))
        self._streak.caption.set_label("day in a row" if s["streak"] == 1 else "days in a row")
        self._week.value.set_label(format_minutes(week_minutes))
        self._week.caption.set_label(f"focused {self._week_label.get_label().lower()}"
                                     if self._offset < 2 else "focused that week")
        self._total.value.set_label(str(s["total_stars"]))
        self._total.caption.set_label("star in all" if s["total_stars"] == 1 else "stars in all")
