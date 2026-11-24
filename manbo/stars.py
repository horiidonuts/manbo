"""The stars dialog: a week of night sky, one constellation per day, and stats."""

import datetime as dt
import math

import cairo

from gi.repository import Adw, Gtk

from .i18n import t, turkish
from .history import (
    by_day, format_minutes, layout_day, star_scale, summary, week_start, _mulberry32,
)
from .themes import THEMES, WHITE, hex_to_rgb, mix, palette



def day_names():
    return (("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz") if turkish()
            else ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))


def month_name(month):
    names = (("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara") if turkish()
             else ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
    return names[month - 1]


def short_date(d):
    return f"{d.day} {month_name(d.month)}" if turkish() else f"{month_name(d.month)} {d.day}"
STAR_R = 8.5           # radius of a 25-minute star, px
LABEL_BAND = 40        # room for the day names under the sky
SKY_HEIGHT = 280
FADE = 150             # px between the week row and the stars: the horizon glow fades out here
# The whole dialog is one twilight sky, painted behind everything (colors taken from an anime
# evening sky, turned upside down): a light yellow glow and a thin band of pink at the horizon
# with a few wisps of cloud, a long fade through mauve and lavender, periwinkle and royal blue
# behind the stars, indigo and navy behind the stats, and all but black violet at the bottom.
# The same in the Android app (StarsSheet.kt).
HORIZON_STOPS = ((0, "#FFF1CF"), (22, "#FFE5DD"), (44, "#FCD1D2"), (66, "#F1C4CF"), (96, "#DFB3CA"),
                 (130, "#C7A1C8"), (170, "#B495CA"), (215, "#A18BCB"), (270, "#817ACC"))   # px from the top
NIGHT_STOPS = ((0.45, "#686AC8"), (0.53, "#4C54C2"), (0.60, "#3741B1"), (0.67, "#2A339C"),
               (0.75, "#1A1F7D"), (0.83, "#0D0F5D"), (0.91, "#070941"), (1.0, "#0D0817"))   # of the height
CLOUD = (1.0, 0.96, 0.93)
HEADER_ROOM = 53       # the header bar (47 px) floats over the top of the sky, plus a little air

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
    """The sky itself is the same twilight for every theme; its stars are the theme's."""
    bg = hex_to_rgb(palette(theme, "focus")["bg"])
    return {"star": mix(bg, WHITE, 0.55)}


def _css_rgb(rgb, alpha=None):
    r, g, b = (round(c * 255) for c in rgb)
    return f"rgba({r}, {g}, {b}, {alpha})" if alpha is not None else f"rgb({r}, {g}, {b})"


def sky_stops(h):
    """The twilight's color stops as (offset 0..1, rgb) for a sky `h` px tall."""
    stops, last = [], -1.0
    for at, color in [(px / max(h, 1), c) for px, c in HORIZON_STOPS] + list(NIGHT_STOPS):
        last = min(1.0, max(at, last + 0.002))
        stops.append((last, hex_to_rgb(color)))
    return stops


def paint_sky(cr, w, h, star):
    """The whole twilight: gradient, wisps of cloud at the horizon, stardust where it's dark."""
    grad = cairo.LinearGradient(0, 0, 0, h)
    for at, rgb in sky_stops(h):
        grad.add_color_stop_rgb(at, *rgb)
    cr.set_source(grad)
    cr.paint()

    rnd = _mulberry32(7)
    for _ in range(4 + int(w / 90)):   # long, flat, soft-edged puffs, thinning out downwards
        cx, cy = rnd() * w, 8 + rnd() ** 1.6 * 170
        fade = max(0.0, 1 - cy / 210)
        for _ in range(3 + int(rnd() * 3)):
            x, y = cx + (rnd() - 0.5) * 160, cy + (rnd() - 0.5) * 14
            rx = 50 + rnd() * 90
            ry = rx * (0.10 + rnd() * 0.08)
            alpha = (0.16 + rnd() * 0.22) * fade
            cr.save()
            cr.translate(x, y)
            cr.scale(rx, ry)
            puff = cairo.RadialGradient(0, 0, 0, 0, 0, 1)
            puff.add_color_stop_rgba(0, *CLOUD, alpha)
            puff.add_color_stop_rgba(1, *CLOUD, 0)
            cr.set_source(puff)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.fill()
            cr.restore()

    for _ in range(int(w * h / 1500)):   # stardust, more of it the darker the sky
        x, y, size = rnd() * w, rnd() * h, 0.5 + rnd() * 0.8
        alpha = (0.15 + rnd() * 0.35) * min(1.0, max(0.0, (y / h - 0.3) / 0.35))
        if alpha > 0.01:
            cr.set_source_rgba(*star, alpha)
            cr.arc(x, y, size, 0, 2 * math.pi)
            cr.fill()


class SkyBackdrop(Gtk.DrawingArea):
    """Paints the twilight behind the whole dialog."""

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self.theme = "blossom"
        self.set_draw_func(lambda _a, cr, w, h: paint_sky(cr, w, h, sky_colors(self.theme)["star"]))


def stars_css():
    """Everything on the twilight is see-through; the stat cards are frosted glass."""
    rules = [
        ".stars-dialog-view, .stars-dialog-view headerbar, .stars-dialog-view scrolledwindow "
        "{ background: none; box-shadow: none; }",
        ".stars-dialog-view headerbar { color: #2A2140; }",
        ".stars-nav { color: #2A2140; }",
    ]
    for key in THEMES:
        star = sky_colors(key)["star"]
        rules.append(
            f".stars-sky.theme-{key} .stars-stat {{ background-color: {_css_rgb(star, 0.1)}; "
            f"color: {_css_rgb(star)}; box-shadow: none; }}"
        )
    return "\n".join(rules)


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

        # (the twilight itself is the SkyBackdrop behind the whole dialog)
        col_w = w / 7
        star_r = min(STAR_R, col_w * 0.1)   # a narrow sky gets smaller stars
        sky_h = h - LABEL_BAND
        self._stars = []
        any_stars = False
        for i in range(7):
            day = self.monday + dt.timedelta(days=i)
            sessions = self.days.get(day, [])
            x0 = i * col_w

            # today: a soft glow behind its column, brightest at its name, fading out at both ends
            if day == today:
                glow = cairo.LinearGradient(0, 0, 0, h)
                glow.add_color_stop_rgba(0, *colors["star"], 0.0)
                glow.add_color_stop_rgba(0.8, *colors["star"], 0.10)
                glow.add_color_stop_rgba(1, *colors["star"], 0.0)
                cr.set_source(glow)
                cr.rectangle(x0 + 4, 0, col_w - 8, h)
                cr.fill()

            # day name
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                cairo.FONT_WEIGHT_BOLD if day == today else cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(11)
            alpha = 0.95 if day == today else (0.35 if day > today else 0.6)
            cr.set_source_rgba(*colors["star"], alpha)
            for text, dy in ((day_names()[i], 17), (str(day.day), 31)):
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
            text = (t("Finish a focus session to light your first star",
                      "İlk yıldızını yakmak için bir odak seansı bitir")
                    if self.monday == week_start(today) else t("No stars this week", "Bu hafta yıldız yok"))
            ext = cr.text_extents(text)
            cr.move_to(w / 2 - ext.x_advance / 2, sky_h / 2)
            cr.show_text(text)

    def _on_tooltip(self, _area, x, y, _keyboard, tooltip):
        best = min(self._stars, key=lambda s: math.hypot(s[0] - x, s[1] - y), default=None)
        if best is None or math.hypot(best[0] - x, best[1] - y) > 16:
            return False
        when = dt.datetime.fromtimestamp(best[2] / 1000)
        tooltip.set_text(f"{day_names()[when.weekday()]} {when:%H:%M} · {format_minutes(best[3])}")
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
        super().__init__(title=t("Your stars", "Yıldızların"), content_width=600, content_height=760)
        self._history = history
        self._settings = settings
        self._offset = 0   # weeks back from this one

        self.sky = SkyView()
        self._prev = Gtk.Button(icon_name="go-previous-symbolic", tooltip_text=t("Previous week", "Önceki hafta"),
                                css_classes=["flat", "circular"])
        self._next = Gtk.Button(icon_name="go-next-symbolic", tooltip_text=t("Next week", "Sonraki hafta"),
                                css_classes=["flat", "circular"])
        self._prev.connect("clicked", lambda *_: self._move(1))
        self._next.connect("clicked", lambda *_: self._move(-1))
        self._week_label = Gtk.Label(css_classes=["heading"], hexpand=True)
        nav = Gtk.Box(spacing=6, css_classes=["stars-nav"])
        nav.append(self._prev)
        nav.append(self._week_label)
        nav.append(self._next)

        self._today = _Stat(t("today", "bugün"))
        self._streak = _Stat(t("days in a row", "gün üst üste"))
        self._week = _Stat(t("this week", "bu hafta"))
        self._total = _Stat(t("stars in all", "toplam yıldız"))
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, column_homogeneous=True)
        grid.attach(self._today, 0, 0, 1, 1)
        grid.attach(self._streak, 1, 0, 1, 1)
        grid.attach(self._week, 0, 1, 1, 1)
        grid.attach(self._total, 1, 1, 1, 1)

        nav.set_margin_start(18)
        nav.set_margin_end(18)
        nav.set_margin_top(HEADER_ROOM)
        grid.set_margin_start(18)
        grid.set_margin_end(18)
        self.sky.set_margin_top(FADE)
        # the sky runs edge to edge and down to the bottom, behind the stats too
        self._sky_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, vexpand=True,
                                css_classes=["stars-sky"])
        self._sky_box.append(self.sky)
        self._sky_box.append(grid)
        # room under the stats: scrolled all the way down, they sit in the middle of the dialog
        self._grid = grid
        self._tail = Gtk.Box()
        self._sky_box.append(self._tail)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(nav)
        box.append(self._sky_box)
        self._theme_class = None

        # The twilight is part of what scrolls, so it moves with the stars and stats. It starts at
        # the very top: the content runs under the (see-through) header bar, which stays put.
        self._backdrop = SkyBackdrop()
        content = Gtk.Overlay(child=self._backdrop)
        content.add_overlay(box)
        content.set_measure_overlay(box, True)
        self._scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        self._scroll.set_child(content)
        self._scroll.get_vadjustment().connect("changed", lambda *_: self._fit_tail())
        view = Adw.ToolbarView(css_classes=["stars-dialog-view"], extend_content_to_top_edge=True)
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(self._scroll)
        self.set_child(view)

        handlers = [(history, history.connect("changed", lambda *_: self._refresh())),
                    (settings, settings.connect("changed", self._on_setting))]
        self.connect("closed", lambda *_: [obj.disconnect(h) for obj, h in handlers])
        self._refresh()

    def _fit_tail(self):
        visible = self._scroll.get_vadjustment().get_page_size() - HEADER_ROOM
        room = max(28, int((visible - self._grid.get_height()) / 2) - 16)   # (16: the box spacing)
        if room != self._tail.get_size_request()[1]:
            self._tail.set_size_request(-1, room)

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
            self._week_label.set_label(t("This week", "Bu hafta"))
        elif self._offset == 1:
            self._week_label.set_label(t("Last week", "Geçen hafta"))
        else:
            sunday = monday + dt.timedelta(days=6)
            self._week_label.set_label(f"{short_date(monday)} – {short_date(sunday)}")
        theme = self._settings["theme"]
        if self._theme_class:
            self._sky_box.remove_css_class(self._theme_class)
        self._theme_class = f"theme-{theme}"
        self._sky_box.add_css_class(self._theme_class)
        self._backdrop.theme = theme
        self._backdrop.queue_draw()
        self.sky.show(monday, days, theme)

        s = summary(sessions, today)
        week_minutes = sum(m for i in range(7) for _e, m in days.get(monday + dt.timedelta(days=i), []))
        stars = s["today_stars"]
        self._today.value.set_label(t(f"{stars} {'star' if stars == 1 else 'stars'}", f"{stars} yıldız"))
        today_text = t("today", "bugün")
        self._today.caption.set_label(f"{today_text} · {format_minutes(s['today_minutes'])}" if stars else today_text)
        self._streak.value.set_label(str(s["streak"]))
        self._streak.caption.set_label(t("day in a row" if s["streak"] == 1 else "days in a row", "gün üst üste"))
        self._week.value.set_label(format_minutes(week_minutes))
        self._week.caption.set_label({
            0: t("focused this week", "bu hafta odak"),
            1: t("focused last week", "geçen hafta odak"),
        }.get(self._offset, t("focused that week", "o hafta odak")))
        self._total.value.set_label(str(s["total_stars"]))
        self._total.caption.set_label(t("star in all" if s["total_stars"] == 1 else "stars in all", "toplam yıldız"))
