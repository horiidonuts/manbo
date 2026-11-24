// Manbo in the GNOME top bar: "● 24:59" with a menu to start/pause, reset,
// switch modes and open the app. Talks to the running Manbo over D-Bus
// (io.github.horiidonuts.Manbo1, see manbo/service.py): reads GetState(),
// follows StateChanged and counts down locally from endTime.

import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Gio from 'gi://Gio';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const BUS_NAME = 'io.github.horiidonuts.Manbo';
const OBJECT_PATH = '/io/github/horiidonuts/Manbo';
const IFACE = 'io.github.horiidonuts.Manbo1';
const MODES = ['focus', 'short', 'long'];
// Manbo's language (Preferences → Language) comes with its state; the system's until then
let turkish = GLib.get_language_names()[0].toLowerCase().startsWith('tr');
const t = (en, tr) => (turkish ? tr : en);
const modeName = mode => ({
    focus: t('Focus', 'Odak'), short: t('Short break', 'Kısa mola'), long: t('Long break', 'Uzun mola'),
})[mode];
const FALLBACK_COLOR = '#F4ACB7';
const HANDOFF_MS = 500;   // same beat as the app: show the finished session, then move on

const ManboIndicator = GObject.registerClass(
class ManboIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.5, 'Manbo');
        this._state = null;
        this._pending = null;
        this._tickId = 0;
        this._handoffId = 0;

        const box = new St.BoxLayout({style_class: 'manbo-box'});
        this._dot = new St.Widget({style_class: 'manbo-dot', y_align: Clutter.ActorAlign.CENTER});
        this._label = new St.Label({
            text: '--:--', style_class: 'manbo-time', y_align: Clutter.ActorAlign.CENTER,
        });
        box.add_child(this._dot);
        box.add_child(this._label);
        this.add_child(box);

        this._header = new PopupMenu.PopupMenuItem('', {reactive: false, style_class: 'manbo-header'});
        this.menu.addMenuItem(this._header);
        this._toggleItem = this.menu.addAction('Start', () => this._call('Toggle'));
        this._resetItem = this.menu.addAction('Reset', () => this._call('Reset'));
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._modeItems = {};
        for (const mode of MODES) {
            this._modeItems[mode] = this.menu.addAction(modeName(mode),
                () => this._call('SelectMode', new GLib.Variant('(s)', [mode])));
        }
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._openItem = this.menu.addAction(t('Open Manbo', "Manbo'yu aç"), () => this._openApp());

        this._signalId = Gio.DBus.session.signal_subscribe(
            BUS_NAME, IFACE, 'StateChanged', OBJECT_PATH, null, Gio.DBusSignalFlags.NONE,
            (_conn, _sender, _path, _iface, _signal, params) => this._apply(params.deepUnpack()[0]));
        this._watchId = Gio.bus_watch_name(Gio.BusType.SESSION, BUS_NAME,
            Gio.BusNameWatcherFlags.NONE, () => this._fetch(), () => this._setState(null));

        this._render();
    }

    // middle click starts/pauses without opening the menu
    vfunc_event(event) {
        if (event.type() === Clutter.EventType.BUTTON_PRESS && event.get_button() === Clutter.BUTTON_MIDDLE) {
            this._call('Toggle');
            return Clutter.EVENT_STOP;
        }
        return super.vfunc_event(event);
    }

    // -- D-Bus ------------------------------------------------------------------

    _fetch() {
        Gio.DBus.session.call(BUS_NAME, OBJECT_PATH, IFACE, 'GetState', null,
            new GLib.VariantType('(s)'), Gio.DBusCallFlags.NO_AUTO_START, -1, null,
            (conn, res) => {
                try {
                    this._apply(conn.call_finish(res).deepUnpack()[0]);
                } catch (e) {
                    this._setState(null);   // an old Manbo without GetState, or gone
                }
            });
    }

    _call(method, args = null) {
        if (!this._state)
            return this._openApp();
        Gio.DBus.session.call(BUS_NAME, OBJECT_PATH, IFACE, method, args, null,
            Gio.DBusCallFlags.NONE, -1, null, (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (e) {
                    logError(e, 'Manbo');
                }
            });
    }

    // starts Manbo through D-Bus activation if needed, and shows its window
    _openApp() {
        Gio.DBus.session.call(BUS_NAME, OBJECT_PATH, 'org.freedesktop.Application', 'Activate',
            new GLib.Variant('(a{sv})', [{}]), null, Gio.DBusCallFlags.NONE, -1, null,
            (conn, res) => {
                try {
                    conn.call_finish(res);
                } catch (e) {
                    logError(e, 'Manbo: could not open the app');
                }
            });
    }

    // -- state ----------------------------------------------------------------

    _apply(json) {
        let next;
        try {
            next = JSON.parse(json);
        } catch (e) {
            return;
        }
        const prev = this._state;
        this._clearHandoff();
        if (prev && prev.running && !next.running && prev.mode !== next.mode) {
            // a session just ended: show it at 00:00 for a beat, then the next one
            this._setState({...prev, running: false, remaining: 0, endTime: 0});
            this._pending = next;
            this._handoffId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, HANDOFF_MS, () => {
                this._handoffId = 0;
                this._setState(this._pending);
                this._pending = null;
                return GLib.SOURCE_REMOVE;
            });
            return;
        }
        this._setState(next);
    }

    _setState(state) {
        this._state = state;
        const running = Boolean(state && state.running);
        if (running && !this._tickId) {
            this._tickId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
                this._render();
                return GLib.SOURCE_CONTINUE;
            });
        } else if (!running && this._tickId) {
            GLib.source_remove(this._tickId);
            this._tickId = 0;
        }
        this._render();
    }

    _remaining() {
        const s = this._state;
        if (!s)
            return 0;
        return s.running ? Math.max(0, Math.ceil((s.endTime - Date.now()) / 1000)) : s.remaining;
    }

    _render() {
        const s = this._state;
        if (s && s.language)
            turkish = s.language === 'tr';
        this._resetItem.label.text = t('Reset', 'Sıfırla');
        this._openItem.label.text = t('Open Manbo', "Manbo'yu aç");
        for (const [mode, item] of Object.entries(this._modeItems))
            item.label.text = modeName(mode);
        const color = s && s.palette ? s.palette.button : FALLBACK_COLOR;
        // filled while running, a ring while paused
        this._dot.set_style(`border-color: ${color}; background-color: ${s && s.running ? color : 'transparent'};`);
        if (!s) {
            this._label.text = '--:--';
            this.add_style_class_name('manbo-offline');
            this._header.label.text = t('Manbo\'s napping 💤', 'Manbo uyuyor 💤');
            this._toggleItem.visible = this._resetItem.visible = false;
            for (const item of Object.values(this._modeItems))
                item.visible = false;
            return;
        }
        this.remove_style_class_name('manbo-offline');
        const secs = this._remaining();
        const m = Math.floor(secs / 60), sec = secs % 60;
        this._label.text = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
        this._header.label.text = t(`${modeName(s.mode)} · ${s.cyclePosition} of ${s.longBreakInterval} sessions`,
            `${modeName(s.mode)} · seans ${s.cyclePosition}/${s.longBreakInterval}`);
        this._toggleItem.visible = this._resetItem.visible = true;
        this._toggleItem.label.text = s.running ? t('Pause', 'Duraklat') : t('Start', 'Başlat');
        for (const [mode, item] of Object.entries(this._modeItems)) {
            item.visible = true;
            item.setOrnament(mode === s.mode ? PopupMenu.Ornament.DOT : PopupMenu.Ornament.NONE);
        }
    }

    _clearHandoff() {
        if (this._handoffId) {
            GLib.source_remove(this._handoffId);
            this._handoffId = 0;
            this._pending = null;
        }
    }

    destroy() {
        this._clearHandoff();
        if (this._tickId) {
            GLib.source_remove(this._tickId);
            this._tickId = 0;
        }
        if (this._signalId) {
            Gio.DBus.session.signal_unsubscribe(this._signalId);
            this._signalId = 0;
        }
        if (this._watchId) {
            Gio.bus_unwatch_name(this._watchId);
            this._watchId = 0;
        }
        super.destroy();
    }
});

export default class ManboExtension extends Extension {
    enable() {
        this._indicator = new ManboIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
