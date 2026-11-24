"""Mode selector: a pill frame with arrows, the labels behind it scroll like a
wheel (cyclic). Click the arrows, drag the text, scroll, or use ←/→.
The pill hugs the current label and smoothly resizes while sliding.
"""

import math

import cairo
from gi.repository import Adw, GObject, Gtk, Pango, PangoCairo

# ---- tuning -------------------------------------------------------------------
SLIDE_MS = 280
SLIDE_EASING = Adw.Easing.EASE_OUT_CUBIC
HEIGHT = 34           # widget height
PILL_H = 32
ARROW_ZONE = 30       # px reserved for each arrow inside the pill
TEXT_PAD = 10         # px between text and arrow zone
FADE = 8              # px of fade at the edges of the text window
GAP = 36              # gap between neighbouring labels on the wheel
FONT_PX = 12
LETTER_SPACING_PX = 2
DRAG_THRESHOLD = 4


class ModeWheel(Gtk.DrawingArea):
    __gtype_name__ = "ManboModeWheel"
    __gsignals__ = {
        "selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, modes):
        """`modes`: list of (key, title) in wheel order."""
        super().__init__(hexpand=True, content_height=HEIGHT)
        self._keys = [k for k, _ in modes]
        self._titles = [t for _, t in modes]
        self._layouts = None
        self._widths = None

        self._pos = 0.0     # float index on an endless strip (index mod n = mode)
        self._target = 0    # integer index the wheel is settling on
        self._anim = None

        self._dragging = False
        self._drag_base = 0.0
        self._press_x = 0.0
        self._pill = (0, 0)  # (x, width) of the last drawn pill, for hit testing

        self.set_draw_func(self._draw)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.DISCRETE
        )
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

    # -- public API ----------------------------------------------------------

    def set_titles(self, titles):
        """New labels in the same order (another language)."""
        self._titles = list(titles)
        self._layouts = None
        self.queue_draw()

    def set_mode(self, key, animate=True):
        n = len(self._keys)
        if self._keys[self._target % n] == key:
            return
        delta = (self._keys.index(key) - self._target) % n
        delta = (delta + n // 2) % n - n // 2   # shortest way round
        self._go_to(self._target + delta, animate=animate)

    def step(self, delta):
        """Move by `delta` labels and report the newly selected mode."""
        self._go_to(self._target + delta, emit=True)

    # -- movement ------------------------------------------------------------

    def _go_to(self, target, emit=False, animate=True):
        n = len(self._keys)
        changed = target % n != self._target % n
        self._target = target
        if self._anim is not None:
            self._anim.pause()
            self._anim = None
        if animate and self.get_mapped():
            anim = Adw.TimedAnimation.new(
                self, self._pos, float(target), SLIDE_MS,
                Adw.CallbackAnimationTarget.new(self._set_pos),
            )
            anim.set_easing(SLIDE_EASING)
            self._anim = anim
            # start inside a frame so the frame clock time is fresh
            self.add_tick_callback(lambda *_: self._play_if_current(anim))
        else:
            self._set_pos(float(target))
        if emit and changed:
            self.emit("selected", self._keys[target % n])

    def _play_if_current(self, anim):
        if anim is self._anim:
            anim.play()
        return False

    def _set_pos(self, value):
        self._pos = value
        self.queue_draw()

    # -- input ---------------------------------------------------------------

    def _slot(self):
        return (max(self._widths) if self._widths else 100) + GAP

    def _arrow_at(self, x):
        px, pw = self._pill
        if px <= x <= px + ARROW_ZONE + 4:
            return -1
        if px + pw - ARROW_ZONE - 4 <= x <= px + pw:
            return 1
        return 0

    def _on_drag_begin(self, _gesture, x, _y):
        self._dragging = False
        self._press_x = x

    def _on_drag_update(self, _gesture, dx, _dy):
        if not self._dragging:
            if abs(dx) < DRAG_THRESHOLD:
                return
            self._dragging = True
            if self._anim is not None:
                self._anim.pause()
                self._anim = None
            self._drag_base = self._pos + dx / self._slot()
            self.set_cursor_from_name("grabbing")
        self._set_pos(self._drag_base - dx / self._slot())

    def _on_drag_end(self, _gesture, dx, _dy):
        if not self._dragging:  # a plain click
            arrow = self._arrow_at(self._press_x + dx)
            if arrow:
                self.step(arrow)
            return
        self._dragging = False
        self.set_cursor_from_name(None)
        target = round(self._pos)
        # a short but deliberate flick still moves one step
        if target == self._target and abs(dx) > self._slot() * 0.15:
            target += -1 if dx > 0 else 1
        self._go_to(target, emit=True)

    def _on_scroll(self, _ctrl, dx, dy):
        d = dy if abs(dy) >= abs(dx) else dx
        if d == 0:
            return False
        self.step(1 if d > 0 else -1)
        return True

    def _on_motion(self, _ctrl, x, y):
        if self._dragging:
            return
        px, pw = self._pill
        inside = px <= x <= px + pw and abs(y - self.get_height() / 2) <= PILL_H / 2
        if not inside:
            self.set_cursor_from_name(None)
        else:
            self.set_cursor_from_name("pointer" if self._arrow_at(x) else "grab")

    # -- drawing -------------------------------------------------------------

    def _ensure_layouts(self):
        if self._layouts is not None:
            return
        desc = self.get_pango_context().get_font_description().copy()
        desc.set_weight(Pango.Weight.ULTRABOLD)
        desc.set_absolute_size(FONT_PX * Pango.SCALE)
        attrs = Pango.AttrList()
        attrs.insert(Pango.attr_letter_spacing_new(LETTER_SPACING_PX * Pango.SCALE))
        self._layouts, self._widths = [], []
        for title in self._titles:
            layout = self.create_pango_layout(title)
            layout.set_font_description(desc)
            layout.set_attributes(attrs)
            w, _h = layout.get_pixel_size()
            self._layouts.append(layout)
            self._widths.append(w - LETTER_SPACING_PX)  # drop trailing spacing

    def _draw(self, _area, cr, w, h):
        self._ensure_layouts()
        n = len(self._keys)
        color = self.get_color()
        rgb = (color.red, color.green, color.blue)
        cx, cy = w / 2, h / 2

        # pill width follows the label currently under the frame
        i0 = math.floor(self._pos)
        frac = self._pos - i0
        text_w = self._widths[i0 % n] + (self._widths[(i0 + 1) % n] - self._widths[i0 % n]) * frac
        pill_w = text_w + 2 * (TEXT_PAD + ARROW_ZONE)
        px, py = cx - pill_w / 2, cy - PILL_H / 2
        self._pill = (px, pill_w)

        # pill frame
        _pill_path(cr, px + 0.75, py + 0.75, pill_w - 1.5, PILL_H - 1.5)
        cr.set_source_rgba(*rgb, 0.10)
        cr.fill_preserve()
        cr.set_source_rgba(*rgb, 0.22)
        cr.set_line_width(1.5)
        cr.stroke()

        # arrows
        cr.set_line_width(2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_source_rgba(*rgb, 0.75)
        a = 4.5
        for ax, sign in ((px + ARROW_ZONE / 2 + 3, -1), (px + pill_w - ARROW_ZONE / 2 - 3, 1)):
            cr.move_to(ax - sign * a / 2, cy - a)
            cr.line_to(ax + sign * a / 2, cy)
            cr.line_to(ax - sign * a / 2, cy + a)
            cr.stroke()

        # the wheel: labels on an endless strip, seen through the text window
        wx0 = px + ARROW_ZONE
        wx1 = px + pill_w - ARROW_ZONE
        slot = self._slot()
        cr.save()
        cr.rectangle(wx0, py, wx1 - wx0, PILL_H)
        cr.clip()
        cr.push_group()
        cr.set_source_rgb(*rgb)
        for j in range(i0 - 1, i0 + 3):
            layout = self._layouts[j % n]
            lw, lh = layout.get_pixel_size()
            x = cx + (j - self._pos) * slot - self._widths[j % n] / 2
            cr.move_to(x, cy - lh / 2)
            PangoCairo.show_layout(cr, layout)
        strip = cr.pop_group()
        fade = cairo.LinearGradient(wx0, 0, wx1, 0)
        span = max(1.0, wx1 - wx0)
        edge = min(0.5, FADE / span)
        fade.add_color_stop_rgba(0, 0, 0, 0, 0)
        fade.add_color_stop_rgba(edge, 0, 0, 0, 1)
        fade.add_color_stop_rgba(1 - edge, 0, 0, 0, 1)
        fade.add_color_stop_rgba(1, 0, 0, 0, 0)
        cr.set_source(strip)
        cr.mask(fade)
        cr.restore()


def _pill_path(cr, x, y, w, h):
    r = h / 2
    cr.new_path()
    cr.arc(x + r, y + r, r, math.pi / 2, 3 * math.pi / 2)
    cr.arc(x + w - r, y + r, r, -math.pi / 2, math.pi / 2)
    cr.close_path()
