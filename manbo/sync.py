"""Phone sync: keeps Manbo on the phone in step with this computer over the LAN.

The computer is the server. Pairing shows a QR code (a manbo://pair URI with
this computer's id, addresses, port and a random key); the phone scans it and
from then on connects here by itself.

Wire protocol: one JSON object per line over TCP.

    phone: {"t":"hello","id":<pc id>,"phone":<phone id>,"name":..,"nonce":n1}
    pc:    {"t":"challenge","nonce":n2,"proof":hmac(key, "manbo1|pc|n1|n2")}
    phone: {"t":"auth","proof":hmac(key, "manbo1|phone|n1|n2")}
    then both: {"t":"state","timer":{..},"durations":{..}} on every change,
    phone: {"t":"ping"} every minute, pc: {"t":"pong"}

Both parts of a state carry a stamp (wall-clock ms of the last user action)
and the id of the device it happened on; the newest one wins. A device that
can't find the computer by the addresses in the QR code asks around with a
UDP broadcast {"t":"find","id":<pc id>} to the same port; the computer
answers {"t":"here","id":..,"port":..}.
"""

import base64
import fcntl
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import struct
import uuid
from urllib.parse import quote, urlencode

from gi.repository import Gio, GLib, GObject

from .timer import MODES

PORT = 47250
IDLE_TIMEOUT_S = 150      # the phone pings every 60 s
MAX_LINE = 16 * 1024

# settings that travel with the timer: wire name -> settings key
DURATIONS = {
    "focus": "focus_minutes",
    "short": "short_break_minutes",
    "long": "long_break_minutes",
    "interval": "long_break_interval",
}


def _proof(key, who, n1, n2):
    return hmac.new(key, f"manbo1|{who}|{n1}|{n2}".encode(), hashlib.sha256).hexdigest()


def _wall_ms():
    return GLib.get_real_time() // 1000


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _newer(a, b):
    """Is stamp/by pair `a` newer than `b`?"""
    return (a.get("stamp", 0), a.get("by", "")) > (b.get("stamp", 0), b.get("by", ""))


def local_addresses():
    """This computer's IPv4 addresses a phone could reach: LAN and Tailscale-style."""
    found = []
    for _index, name in socket.if_nameindex():
        if name == "lo" or name.startswith(("docker", "virbr", "veth", "podman", "br-")):
            continue
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                packed = fcntl.ioctl(s.fileno(), 0x8915,  # SIOCGIFADDR
                                     struct.pack("256s", name[:15].encode()))
        except OSError:
            continue  # no IPv4 address
        ip = ipaddress.IPv4Address(packed[20:24])
        if ip.is_private or ip in ipaddress.IPv4Network("100.64.0.0/10"):
            if not ip.is_link_local:
                found.append(str(ip))
    # LAN addresses first: they're the ones the phone tries first
    return sorted(found, key=lambda a: a.startswith("100."))


def computer_name():
    try:
        with open("/etc/machine-info", encoding="utf-8") as f:
            for line in f:
                if line.startswith("PRETTY_HOSTNAME="):
                    name = line.split("=", 1)[1].strip().strip('"')
                    if name:
                        return name
    except OSError:
        pass
    return GLib.get_host_name()


class _Peer:
    """One phone connection."""

    def __init__(self, server, conn):
        self.server = server
        self.conn = conn
        self.name = "phone"
        self.authed = False
        self._n1 = self._n2 = ""
        self._cancel = Gio.Cancellable()
        sock = conn.get_socket()
        sock.set_timeout(IDLE_TIMEOUT_S)   # a phone that went away times out
        sock.set_keepalive(True)
        self._in = Gio.DataInputStream.new(conn.get_input_stream())
        self._out = conn.get_output_stream()
        self._read()

    def _read(self):
        self._in.read_line_async(GLib.PRIORITY_DEFAULT, self._cancel, self._on_line)

    def _on_line(self, stream, result):
        try:
            line, _length = stream.read_line_finish_utf8(result)
        except GLib.Error:
            line = None
        if line is None:
            return self.close()
        if len(line) > MAX_LINE:
            return self.close()
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                raise ValueError
            self._handle(msg)
        except (ValueError, KeyError, TypeError) as e:
            print(f"manbo: sync: bad message from {self.name}: {e!r}")
            return self.close()
        if not self._cancel.is_cancelled():
            self._read()

    def _handle(self, msg):
        t = msg.get("t")
        key = self.server.key
        if not self.authed:
            if t == "hello" and not self._n2:
                if msg["id"] != self.server.id or key is None:
                    return self.close()
                self._n1 = str(msg["nonce"])
                self._n2 = secrets.token_hex(16)
                self.name = str(msg.get("name") or "phone")[:60]
                self.send({"t": "challenge", "nonce": self._n2,
                           "proof": _proof(key, "pc", self._n1, self._n2)})
            elif t == "auth" and self._n2:
                if not hmac.compare_digest(str(msg["proof"]), _proof(key, "phone", self._n1, self._n2)):
                    print(f"manbo: sync: {self.name} has the wrong key (paired with another code?)")
                    return self.close()
                self.authed = True
                self.server.peer_ready(self)
            else:
                return self.close()
        elif t == "state":
            self.server.apply_remote(msg)
        elif t == "ping":
            self.send({"t": "pong"})

    def send(self, msg):
        data = (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        try:
            self._out.write_all(data, self._cancel)
        except GLib.Error as e:
            print(f"manbo: sync: lost {self.name}: {e.message}")
            self.close()

    def close(self):
        if self._cancel.is_cancelled():
            return
        self._cancel.cancel()
        try:
            self.conn.close(None)
        except GLib.Error:
            pass
        self.server.peer_gone(self)


class SyncServer(GObject.Object):
    """Serves paired phones; started once a phone has been paired."""

    __gsignals__ = {
        "peers-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, timer, settings):
        super().__init__()
        self._timer = timer
        self._settings = settings
        self._path = os.path.join(GLib.get_user_config_dir(), "manbo", "sync.json")
        self._conf = self._load()
        if "id" not in self._conf:
            self._conf["id"] = uuid.uuid4().hex
            self._save()
        timer.local_id = self.id
        self._durations = self._conf.get("durations", {"stamp": 0, "by": ""})
        self._applying = False
        self._service = None
        self._udp = None
        self._udp_source = 0
        self._peers = []
        timer.connect("changed", lambda *_: self._broadcast())
        settings.connect("changed", self._on_settings_changed)
        if self.paired:
            self.start()

    # -- pairing ---------------------------------------------------------------

    @property
    def id(self):
        return self._conf["id"]

    @property
    def key(self):
        k = self._conf.get("key")
        return _unb64(k) if k else None

    @property
    def paired(self):
        return bool(self._conf.get("key"))

    @property
    def port(self):
        return self._port if self._service else PORT

    @property
    def phones(self):
        return [p.name for p in self._peers if p.authed]

    def pairing_uri(self):
        """The QR code's content. Makes a key the first time and starts serving."""
        if not self.paired:
            self._conf["key"] = _b64(secrets.token_bytes(32))
            self._save()
        self.start()
        query = urlencode({
            "v": 1, "id": self.id, "name": computer_name(), "key": self._conf["key"],
            "port": self.port, "ip": ",".join(local_addresses()),
        }, quote_via=quote)
        return f"manbo://pair?{query}"

    def forget(self):
        """Unpair every phone: a new code is needed to pair again."""
        self._conf.pop("key", None)
        self._save()
        self.stop()

    # -- serving ---------------------------------------------------------------

    def start(self):
        if self._service:
            return
        self._service = Gio.SocketService()
        try:
            self._service.add_inet_port(PORT, None)
            self._port = PORT
        except GLib.Error:   # taken: any port will do, discovery tells the phone
            self._port = self._service.add_any_inet_port(None)
        self._service.connect("incoming", self._on_incoming)
        self._service.start()
        try:
            self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp.bind(("0.0.0.0", PORT))
            self._udp_source = GLib.unix_fd_add_full(
                GLib.PRIORITY_DEFAULT, self._udp.fileno(), GLib.IOCondition.IN, self._on_udp)
        except OSError as e:
            print(f"manbo: sync: no discovery ({e})")
            self._udp = None

    def stop(self):
        for peer in list(self._peers):
            peer.close()
        if self._service:
            self._service.stop()
            self._service.close()
            self._service = None
        if self._udp_source:
            GLib.source_remove(self._udp_source)
            self._udp_source = 0
        if self._udp:
            self._udp.close()
            self._udp = None

    def _on_incoming(self, _service, conn, _source):
        self._peers.append(_Peer(self, conn))
        return True

    def _on_udp(self, _fd, _condition):
        try:
            data, addr = self._udp.recvfrom(2048)
            msg = json.loads(data)
            if msg.get("t") == "find" and msg.get("id") == self.id and self.paired:
                reply = {"t": "here", "id": self.id, "port": self.port}
                self._udp.sendto(json.dumps(reply).encode(), addr)
        except (OSError, ValueError, AttributeError):
            pass
        return GLib.SOURCE_CONTINUE

    def peer_ready(self, peer):
        print(f"manbo: sync: {peer.name} connected")
        peer.send(self._state())
        self.emit("peers-changed")

    def peer_gone(self, peer):
        if peer in self._peers:
            self._peers.remove(peer)
            if peer.authed:
                print(f"manbo: sync: {peer.name} disconnected")
                self.emit("peers-changed")

    def shutdown(self):
        self.stop()

    # -- state -------------------------------------------------------------------

    def _state(self):
        durations = {wire: self._settings[key] for wire, key in DURATIONS.items()}
        durations.update(stamp=self._durations["stamp"], by=self._durations["by"])
        return {"t": "state", "timer": self._timer.get_state(), "durations": durations}

    def _broadcast(self):
        if self._applying:
            return
        msg = None
        for peer in list(self._peers):
            if peer.authed:
                msg = msg or self._state()
                peer.send(msg)

    def apply_remote(self, msg):
        timer = msg.get("timer")
        durations = msg.get("durations")
        self._applying = True
        try:
            if isinstance(durations, dict) and _newer(durations, self._durations):
                for wire, key in DURATIONS.items():
                    self._settings.set(key, int(durations[wire]))
                self._durations = {"stamp": int(durations["stamp"]), "by": str(durations["by"])}
                self._conf["durations"] = self._durations
                self._save()
            if isinstance(timer, dict) and timer.get("mode") in MODES:
                mine = self._timer.get_state()
                # the phone ended the session we're both running: end it here too, chime included
                if mine["running"] and not timer["running"] and timer["stamp"] == mine["endAt"]:
                    self._timer.finish_now()
                    mine = self._timer.get_state()
                if _newer(timer, mine):
                    self._timer.set_state({
                        "mode": timer["mode"], "running": bool(timer["running"]),
                        "endAt": int(timer["endAt"]), "remainingMs": max(0, int(timer["remainingMs"])),
                        "started": bool(timer["started"]), "completed": max(0, int(timer["completed"])),
                        "stamp": int(timer["stamp"]), "by": str(timer["by"]),
                    })
        finally:
            self._applying = False
        self._broadcast()   # other phones, if any (the sender ignores what it already has)

    def _on_settings_changed(self, _settings, key):
        if key in DURATIONS.values() and not self._applying:
            self._durations = {"stamp": _wall_ms(), "by": self.id}
            self._conf["durations"] = self._durations
            self._save()
            self._broadcast()

    # -- storage -------------------------------------------------------------------

    def _load(self):
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            tmp = self._path + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)  # holds the key
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._conf, f, indent=2)
            os.replace(tmp, self._path)
        except OSError as e:
            print(f"manbo: sync: could not save {self._path}: {e}")
