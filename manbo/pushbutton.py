"""The big orthographic-3D push button.

It is drawn with Cairo as a cylinder sitting in a round housing, seen from
above at an angle (orthographic projection: circles become ellipses with
ratio sin(angle), vertical heights are scaled by cos(angle)).
`_p` is the press amount: 0 = fully up, 1 = fully sunk.
"""

import math

import cairo

from gi.repository import Adw, Gdk, GObject, Gtk

from .themes import WHITE, hex_to_rgb, luminance, mix

# ---- animation tuning (tweak freely) -----------------------------------------
PRESS_MS = 150                          # sink when starting
PRESS_EASING = Adw.Easing.EASE_OUT_BACK
POP_MS = 100                            # pop up (time over, pause, reset, mode switch)
POP_BOUNCE = 0.12      # rebound height of the pop: 0 = none, 0.25 = classic ease-out-bounce
COLOR_MS = 450                          # palette cross-fade between modes

# ---- shape tuning (all relative to button radius r) --------------------------
VIEW_ANGLE = 27        # camera elevation in degrees (lower = flatter, more side)
BUTTON_WIDTH = 0.8     # button + frame diameter scale (heights stay the same)
BUTTON_HEIGHT = 0.66   # how far the button sticks out of the housing when up
BUTTON_HEIGHT_DOWN = 0.09  # ...and when fully pressed
HOUSING_HEIGHT = 0.15  # housing side height
HOUSING_R = 1.22       # housing radius
HOLE_R = 1.045         # hole the button sits in

SQUASH = math.sin(math.radians(VIEW_ANGLE))   # ellipse y/x ratio
HEIGHT_SCALE = math.cos(math.radians(VIEW_ANGLE))


def bounce_out(t, height):
    """Ease-out-bounce with an adjustable rebound (0..1 -> 0..1).

    Modelled as a ball dropped onto the end value: the first rebound reaches
    `height`, every following one `height` times the previous. height = 0.25
    gives exactly the classic (Penner / libadwaita) ease-out-bounce.
    """
    e = math.sqrt(max(0.0, min(height, 0.9)))   # restitution
    segments = [1.0]                            # fall, then each rebound (in fall units)
    k = e
    while k * k > 0.005 and len(segments) < 6:   # drop invisible micro-bounces
        segments.append(2 * k)
        k *= e
    x = t * sum(segments)
    if x < 1.0:
        return x * x
    x -= 1.0
    peak = e
    for duration in segments[1:]:
        if x < duration:
            u = x - duration / 2
            return 1 - (peak * peak - u * u)
        x -= duration
        peak *= e
    return 1.0


def _ellipse(cr, cx, cy, rx, ry):
    cr.new_path()
    cr.save()
    cr.translate(cx, cy)
    cr.scale(rx, ry)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()


def _cylinder_side(cr, cx, ytop, ybot, rx, ry):
    """Path of the visible side of a vertical cylinder (top face excluded)."""
    cr.new_path()
    cr.move_to(cx - rx, ytop)
    cr.line_to(cx - rx, ybot)
    cr.save()
    cr.translate(cx, ybot)
    cr.scale(rx, ry)
    cr.arc_negative(0, 0, 1, math.pi, 0)  # front half of the bottom ellipse
    cr.restore()
    cr.line_to(cx + rx, ytop)
    cr.close_path()


class PushButton(Gtk.DrawingArea):
    __gtype_name__ = "ManboPushButton"
    __gsignals__ = {
        "activated": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "down-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),  # True = sinking
    }

    def __init__(self):
        super().__init__(hexpand=True, vexpand=True)
        self.set_size_request(220, 220)
        self.set_draw_func(self._draw)

        self._down = False
        self._p = 0.0
        self._geom = None
        self._hover = False

        self._colors = None
        self._color_from = None
        self._color_to = None

        self._press_anim = None
        self._color_anim = Adw.TimedAnimation.new(
            self, 0.0, 1.0, COLOR_MS,
            Adw.CallbackAnimationTarget.new(self._on_color_value),
        )
        self._color_anim.set_easing(Adw.Easing.EASE_OUT_CUBIC)

        click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_pressed)
        self.add_controller(click)

        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", lambda *_: self._set_hover(False))
        self.add_controller(motion)

    # -- public API ----------------------------------------------------------

    @property
    def down(self):
        return self._down

    def set_down(self, down):
        """Animate to the down (sunk) or up (popped) state."""
        if down == self._down:
            return
        self._down = down
        self.emit("down-changed", down)
        if self._press_anim is not None:
            self._press_anim.pause()

        if down:
            anim = Adw.TimedAnimation.new(
                self, self._p, 1.0, PRESS_MS,
                Adw.CallbackAnimationTarget.new(self._on_press_value),
            )
            anim.set_easing(PRESS_EASING)
        else:
            # libadwaita's bounce has a fixed rebound, so drive our own curve
            start = self._p
            anim = Adw.TimedAnimation.new(
                self, 0.0, 1.0, POP_MS,
                Adw.CallbackAnimationTarget.new(
                    lambda t: self._on_press_value(start * (1 - bounce_out(t, POP_BOUNCE)))
                ),
            )
            anim.set_easing(Adw.Easing.LINEAR)
        self._press_anim = anim
        # Start inside the next frame: outside a frame the frame clock reports
        # the *last* frame's time, which can be ~1s stale while the window is
        # idle — that would make short animations (like the pop) skip ahead.
        self.add_tick_callback(lambda *_: self._play_if_current(anim))

    def _play_if_current(self, anim):
        if anim is self._press_anim:
            anim.play()
        return False

    def set_palette(self, bg, button, text, animate=True):
        target = {"bg": hex_to_rgb(bg), "button": hex_to_rgb(button), "text": hex_to_rgb(text)}
        if self._colors is None or not animate:
            self._color_anim.pause()
            self._colors = target
            self.queue_draw()
            return
        self._color_from = dict(self._colors)
        self._color_to = target
        self._color_anim.reset()
        self.add_tick_callback(lambda *_: self._color_anim.play() or False)

    # -- animation targets ---------------------------------------------------

    def _on_press_value(self, value):
        self._p = value
        self.queue_draw()

    def _on_color_value(self, t):
        if self._color_from is None:
            return
        self._colors = {k: mix(self._color_from[k], self._color_to[k], t) for k in self._color_to}
        self.queue_draw()

    # -- input ---------------------------------------------------------------

    def _on_pressed(self, gesture, n_press, x, y):
        if self._hit(x, y):
            gesture.set_state(Gtk.EventSequenceState.CLAIMED)
            self.emit("activated")

    def _on_motion(self, _ctrl, x, y):
        self._set_hover(self._hit(x, y))

    def _set_hover(self, hover):
        if hover != self._hover:
            self._hover = hover
            self.set_cursor_from_name("pointer" if hover else None)

    def _hit(self, x, y):
        g = self._geom
        if g is None:
            return False
        cx, cb, r, k = g["cx"], g["cb"], g["r"], SQUASH
        rb = r * BUTTON_WIDTH
        R = rb * HOUSING_R
        ytop = cb - r * BUTTON_HEIGHT * HEIGHT_SCALE
        in_ellipse = lambda ex, ey, rx, ry: ((x - ex) / rx) ** 2 + ((y - ey) / ry) ** 2 <= 1
        return (
            in_ellipse(cx, cb, R, R * k)
            or in_ellipse(cx, ytop, rb, rb * k)
            or (abs(x - cx) <= rb and ytop <= y <= cb)
        )

    # -- drawing -------------------------------------------------------------

    def _layout(self, w, h):
        k = SQUASH
        above = BUTTON_HEIGHT * HEIGHT_SCALE + BUTTON_WIDTH * k   # from housing center up, in r
        below = BUTTON_WIDTH * HOUSING_R * k + HOUSING_HEIGHT * HEIGHT_SCALE + 0.04
        r = min(w * 0.34, h * 0.92 / (above + below))
        cb = h / 2 + r * (above - below) / 2
        self._geom = {"cx": w / 2, "cb": cb, "r": r}
        return self._geom

    def _draw(self, _area, cr, w, h):
        if self._colors is None:
            return
        g = self._layout(w, h)
        cx, cb, r = g["cx"], g["cb"], g["r"]
        k = SQUASH
        rb = r * BUTTON_WIDTH  # horizontal radius of the button
        R = rb * HOUSING_R

        bg = self._colors["bg"]
        btn = self._colors["button"]
        text = self._colors["text"]

        # housing: side + top
        _cylinder_side(cr, cx, cb, cb + r * HOUSING_HEIGHT * HEIGHT_SCALE, R, R * k)
        cr.set_source_rgb(*mix(bg, text, 0.28))
        cr.fill()

        _ellipse(cr, cx, cb, R, R * k)
        cr.set_source_rgb(*mix(bg, WHITE, 0.45))
        cr.fill()

        # hole the button sits in
        hr = rb * HOLE_R
        _ellipse(cr, cx, cb, hr, hr * k)
        cr.set_source_rgb(*mix(bg, text, 0.45))
        cr.fill()

        # button (the back-out overshoot may push _p a bit past 1)
        height = BUTTON_HEIGHT - (BUTTON_HEIGHT - BUTTON_HEIGHT_DOWN) * self._p
        ytop = cb - r * max(0.0, height) * HEIGHT_SCALE

        _cylinder_side(cr, cx, ytop, cb, rb, rb * k)
        cr.set_source_rgb(*mix(mix(btn, (0, 0, 0), 0.22), text, 0.18))
        cr.fill()

        _ellipse(cr, cx, ytop, rb, rb * k)
        cr.set_source_rgb(*btn)
        cr.fill()

        self._draw_icon(cr, cx, ytop, rb, btn, text)

    def _draw_icon(self, cr, cx, cy, r, btn, text):
        icon = mix(btn, text, 0.75) if luminance(btn) > 0.68 else mix(btn, WHITE, 0.9)
        s = r * 0.42

        cr.save()
        cr.translate(cx, cy)
        cr.scale(1, SQUASH)  # lay the icon flat on the top face
        cr.new_path()
        if self._down:  # pause bars
            bw, bh, gap = s * 0.24, s * 0.9, s * 0.38
            for x0 in (-gap / 2 - bw, gap / 2):
                _round_rect(cr, x0, -bh / 2, bw, bh, bw * 0.4)
        else:           # play triangle, nudged right for optical centering
            cr.move_to(-s * 0.32, -s * 0.5)
            cr.line_to(-s * 0.32, s * 0.5)
            cr.line_to(s * 0.52, 0)
            cr.close_path()
        cr.set_source_rgb(*icon)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(s * 0.16)
        cr.fill_preserve()
        cr.stroke()
        cr.restore()


def _round_rect(cr, x, y, w, h, rad):
    cr.new_sub_path()
    cr.arc(x + w - rad, y + rad, rad, -math.pi / 2, 0)
    cr.arc(x + w - rad, y + h - rad, rad, 0, math.pi / 2)
    cr.arc(x + rad, y + h - rad, rad, math.pi / 2, math.pi)
    cr.arc(x + rad, y + rad, rad, math.pi, 3 * math.pi / 2)
    cr.close_path()
