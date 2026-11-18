# Manbo

A tiny pastel Pomodoro timer for Linux (GTK4 + libadwaita), with a big
orthographic 3D push button in the middle.

- Focus 25 min → short break 5 min, long break 15 min every 4 focus sessions
  (all configurable in Preferences)
- Seven pastel themes: **Blossom**, **Cotton Candy**, **Coastal**, **Frosty**,
  **Periwinkle**, **Golden Summer**, **Autumn**
- Rolling digits: the clock rolls down as time passes and back up on reset
  (can be turned off in Preferences)
- Mode wheel at the top: click the arrows, drag, scroll or use ←/→
- The button sinks when you start (back-out, 150 ms) and pops up when you
  pause or the session ends (soft bounce-out, 100 ms), with click sounds
- Chime when a session ends — Off / Short / Normal / Long, adjustable volume —
  plus a desktop notification while the window is in the background (it gets
  through Do Not Disturb). Sounds live in [`data/sounds/`](data/sounds/README.md)
- Mini mode: a small always-on-top pill with the time and start/pause — opens
  in the top-right corner, drag it anywhere (always-on-top needs KDE Plasma)
- Plasma widget: a small `● 24:59` on the panel (click for the card,
  middle-click to start/pause), or a little Manbo on the desktop with the
  button, rolling clock and session dots. Right-click the desktop or panel →
  *Add Widgets…* → search "Manbo"
- GNOME top bar (e.g. Ubuntu): a small `● 24:59` with a menu to start/pause,
  reset, switch modes and open Manbo (GNOME 45–50). After installing, log out
  and back in once, then turn on **Manbo** in the *Extensions* app (or run
  `gnome-extensions enable manbo@horiidonuts.github.io`)
- Optional: Do Not Disturb while a focus session runs (other notifications are
  held back; Manbo's own session-end alert still comes through)
- Optional: keep running in the background when the window is closed
- Optional: bring the window to the front a second before a session ends,
  without taking keyboard focus (KDE Plasma; uses a small KWin script)

## Keyboard

| Key | Action |
| --- | --- |
| <kbd>Space</kbd> / <kbd>Enter</kbd> | Start / pause |
| <kbd>←</kbd> / <kbd>→</kbd> | Switch mode (Focus / Short break / Long break) |
| <kbd>Ctrl</kbd>+<kbd>M</kbd> | Mini mode on / off |
| <kbd>Esc</kbd> | Leave mini mode |
| <kbd>Ctrl</kbd>+<kbd>,</kbd> | Preferences |
| <kbd>Ctrl</kbd>+<kbd>Q</kbd> | Quit |

## D-Bus API

The running app exports `io.github.horiidonuts.Manbo1` at
`/io/github/horiidonuts/Manbo` on the bus name `io.github.horiidonuts.Manbo`,
for widgets and scripts. Properties: `Mode`, `Running`, `Remaining`,
`EndTime` (Unix ms), `Duration`, `CompletedSessions`, `Version` — with
`PropertiesChanged` on every state change. Methods: `Toggle`, `Start`, `Pause`,
`Reset`, `SelectMode(s)`, `GetState() → s` (all of the above as JSON).
Signals: `Finished(s finished, s next)`, `StateChanged(s json)`. Palette,
`CyclePosition` and `LongBreakInterval` are there for widgets. Manbo is
D-Bus activatable, so calling a method starts it if it isn't running.

```sh
gdbus call --session --dest io.github.horiidonuts.Manbo \
    --object-path /io/github/horiidonuts/Manbo \
    --method io.github.horiidonuts.Manbo1.Toggle
```

## Android

Manbo for Android (Android 8.0+) has the same look, sounds and button. Get the
APK from the [releases](https://github.com/horiidonuts/manbo/releases).

- Keeps counting with the app closed: an ongoing countdown notification and a
  chime + notification when the session ends ("Start short break" right from it)
- The countdown is a Live Update (Android 16+). On Samsung phones it shows in
  the Now Bar once *Developer options → Live notifications for all apps* is on
- Optional Do Not Disturb while focusing (Android asks once for access)
- Button and mode-switch sounds follow the media volume

### Sync with your computer

Pair the phone with Manbo on your PC and the two stay in step: start, pause,
skip or reset on either one, and Do Not Disturb follows on both. Timer lengths
are shared too; the chime plays on the PC while they're connected.

1. On the PC: *Preferences → Phone → Show code*
2. Scan the QR code with the phone's camera, or in Manbo: *Settings → Scan code*
3. Allow *Nearby devices* when Android asks (it's how Android 17 guards the
   local network)

Both need to be on the same network (a Tailscale address works too). The phone
stays connected in the background with a quiet notification; turn off *Stay
connected in background* to sync only while the app is open. Sync uses TCP and
UDP port 47250 on the PC (Fedora's default firewall already allows it).

Build it with `cd android && ./gradlew assembleRelease` (needs the Android SDK;
the sound files are copied from `data/sounds/` at build time).

## Run from source

```sh
git clone https://github.com/horiidonuts/manbo.git
cd manbo
make run          # or: python3 -m manbo
```

Needs `python3-gobject`, `python3-cairo`, `gtk4`, `libadwaita`,
`gstreamer1-plugins-base` and `gstreamer1-plugins-good` (all preinstalled on
Fedora Workstation).

## Build & install the RPM (Fedora)

```sh
sudo dnf install rpm-build desktop-file-utils
make rpm
sudo dnf install ./build/rpm/RPMS/noarch/manbo-*.noarch.rpm
```

Settings are stored in `~/.config/manbo/settings.json`.

## Tweaking

- Animation timings/easings, button size and view angle: top of `manbo/pushbutton.py`
- Palettes: `manbo/themes.py`
- Sound files, volumes and chime lengths: `manbo/sounds.py`

## License

[MIT](LICENSE) © horiidonuts
