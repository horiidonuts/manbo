"""The big MM:SS clock. Each character sits in its own slot; when a digit
changes it rolls like an odometer: down while counting down, up when the
time jumps up (reset, mode switch, next session).
"""

from gi.repository import Gdk, Graphene, Gsk, Gtk

ROLL_MS = 260          # one digit rolling over (a tick is 1000 ms)
JUMP_MS = 380          # rolling back up on reset / mode switch
FADE_PX = 16           # rolling digits fade out over this much at the top/bottom
                       # edge (inside the line's empty space, static digits are untouched)


def _stop(offset, alpha):
    stop = Gsk.ColorStop()
    stop.offset = offset
    stop.color = Gdk.RGBA(red=0, green=0, blue=0, alpha=alpha)
    return stop


class TimeDisplay(Gtk.Box):
    __gtype_name__ = "ManboTimeDisplay"

    def __init__(self):
        super().__init__(halign=Gtk.Align.CENTER, css_classes=["time-label"])
        self._slots = []   # one Gtk.Stack per character
        self._text = ""
        self._seconds = None

    @property
    def text(self):
        return self._text

    def set_seconds(self, secs, animate=True):
        text = f"{secs // 60:02d}:{secs % 60:02d}"
        if text == self._text:
            return
        going_up = self._seconds is not None and secs > self._seconds
        self._seconds = secs
        if len(text) != len(self._slots):   # e.g. 99:59 -> 100:00: rebuild, no roll
            self._rebuild(len(text))
            animate = False
        if going_up:
            transition, duration = Gtk.StackTransitionType.SLIDE_UP, JUMP_MS
        else:
            transition, duration = Gtk.StackTransitionType.SLIDE_DOWN, ROLL_MS
        for slot, old, new in zip(self._slots, self._text.ljust(len(text)), text):
            if old != new:
                self._show(slot, new, transition if animate else Gtk.StackTransitionType.NONE, duration)
        self._text = text
        self.update_property([Gtk.AccessibleProperty.LABEL], [text])

    def do_snapshot(self, snapshot):
        w, h = self.get_width(), self.get_height()
        if h <= 2 * FADE_PX:
            Gtk.Box.do_snapshot(self, snapshot)
            return
        edge = FADE_PX / h
        snapshot.push_mask(Gsk.MaskMode.ALPHA)
        snapshot.append_linear_gradient(
            Graphene.Rect().init(0, 0, w, h),
            Graphene.Point().init(0, 0), Graphene.Point().init(0, h),
            [_stop(0, 0), _stop(edge, 1), _stop(1 - edge, 1), _stop(1, 0)],
        )
        snapshot.pop()
        Gtk.Box.do_snapshot(self, snapshot)
        snapshot.pop()

    def _rebuild(self, n):
        for slot in self._slots:
            self.remove(slot)
        self._slots = []
        self._text = ""
        for _ in range(n):
            slot = Gtk.Stack(vhomogeneous=True, hhomogeneous=True, interpolate_size=False)
            self.append(slot)
            self._slots.append(slot)

    def _show(self, slot, char, transition, duration):
        old = slot.get_visible_child()  # before add_child: the first page becomes visible on its own
        label = Gtk.Label(label=char)
        slot.add_child(label)
        slot.set_transition_type(transition)
        slot.set_transition_duration(duration)
        slot.set_visible_child(label)
        # drop every page except the new one once the roll has finished
        for child in list(_children(slot)):
            if child is not label and child is not old:
                slot.remove(child)
        if old is not None:
            if transition == Gtk.StackTransitionType.NONE or not slot.get_mapped():
                slot.remove(old)
            else:
                slot.connect("notify::transition-running", _drop_hidden)


def _children(widget):
    child = widget.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        yield child
        child = nxt


def _drop_hidden(slot, _pspec):
    if slot.get_transition_running():
        return
    slot.disconnect_by_func(_drop_hidden)
    visible = slot.get_visible_child()
    for child in list(_children(slot)):
        if child is not visible:
            slot.remove(child)
