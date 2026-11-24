"""The "Pair a phone" dialog: a QR code for Manbo on the phone to scan."""

from gi.repository import Adw, GLib, Gtk

from .i18n import t

try:
    import qrcode
except ImportError:   # python3-qrcode missing: the dialog says so
    qrcode = None

QUIET_ZONE = 4   # modules of white around the code, as the QR spec asks
SIZE = 260


def _matrix(text):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0)
    qr.add_data(text)
    qr.make(fit=True)
    return qr.get_matrix()


class PairDialog(Adw.Dialog):
    def __init__(self, sync):
        super().__init__(title=t("Pair a phone", "Telefon eşleştir"), content_width=360)
        self._sync = sync

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=12, margin_bottom=24, margin_start=24, margin_end=24)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        toolbar.set_content(box)
        self.set_child(toolbar)

        steps = Gtk.Label(
            label=t("Scan this with your phone's camera, or in Manbo on the phone: "
                    "Settings → <b>Scan code</b>.",
                    "Bunu telefonun kamerasıyla ya da telefondaki Manbo'da tara: "
                    "Ayarlar → <b>Kodu tara</b>."),
            use_markup=True, wrap=True, justify=Gtk.Justification.CENTER,
        )
        box.append(steps)

        if qrcode is None:
            box.append(Gtk.Label(
                label=t("The QR code needs the python3-qrcode package.", "QR kod için python3-qrcode paketi gerekiyor."),
                css_classes=["error"], wrap=True,
            ))
        else:
            self._modules = _matrix(sync.pairing_uri())
            code = Gtk.DrawingArea(content_width=SIZE, content_height=SIZE, halign=Gtk.Align.CENTER)
            code.set_draw_func(self._draw)
            box.append(code)

        self._status = Gtk.Label(css_classes=["dim-label"], wrap=True, justify=Gtk.Justification.CENTER)
        box.append(self._status)
        box.append(Gtk.Label(
            label=t("Both need to be on the same Wi-Fi (or the phone's hotspot) 📶",
                    "İkisi aynı Wi-Fi'de (ya da telefonun hotspot'unda) olmalı 📶"),
            css_classes=["dim-label", "caption"], wrap=True,
        ))

        self._known = set(sync.phones)
        self._handler = sync.connect("peers-changed", self._on_peers)
        self.connect("closed", lambda *_: sync.disconnect(self._handler))
        self._update_status()

    def _draw(self, _area, cr, width, height):
        n = len(self._modules) + 2 * QUIET_ZONE
        cell = min(width, height) // n
        x0 = (width - cell * n) // 2
        y0 = (height - cell * n) // 2
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(x0, y0, cell * n, cell * n)
        cr.fill()
        cr.set_source_rgb(0, 0, 0)
        for r, row in enumerate(self._modules):
            for c, dark in enumerate(row):
                if dark:
                    cr.rectangle(x0 + (c + QUIET_ZONE) * cell, y0 + (r + QUIET_ZONE) * cell, cell, cell)
        cr.fill()

    def _on_peers(self, *_):
        self._update_status()

    def _update_status(self):
        phones = self._sync.phones
        new = [p for p in phones if p not in self._known]
        if new:
            self._status.set_markup(t("<b>Paired with {}!</b> 🎉", "<b>{} ile eşleştin!</b> 🎉").format(GLib.markup_escape_text(new[0])))
            self._status.remove_css_class("dim-label")
            self._status.add_css_class("success")
        elif phones:
            self._status.set_label(t("Connected with {} 💞", "{} ile bağlı 💞").format(", ".join(phones)))
        else:
            self._status.set_label(t("Waiting for your phone… 📱", "Telefonunu bekliyorum… 📱"))
