# Manbo

A tiny pastel Pomodoro timer for Linux (GTK4 + libadwaita), with a big
orthographic 3D push button in the middle.

- Focus 25 min → short break 5 min, long break 15 min every 4 focus sessions
  (all configurable in Preferences)
- Three pastel themes: **Blossom**, **Cotton Candy**, **Coastal**
- Rolling digits: the clock rolls down as time passes and back up on reset
  (can be turned off in Preferences)
- Mode wheel at the top: click the arrows, drag, scroll or use ←/→
- The button sinks when you start (back-out, 150 ms) and pops up when you
  pause or the session ends (soft bounce-out, 100 ms), with click sounds
- Chime when a session ends — Off / Short / Normal / Long, adjustable volume —
  plus a desktop notification while the window is in the background (it gets
  through Do Not Disturb). Sounds live in [`data/sounds/`](data/sounds/README.md)
- Optional: bring the window to the front a second before a session ends,
  without taking keyboard focus (KDE Plasma; uses a small KWin script)

## Keyboard

| Key | Action |
| --- | --- |
| <kbd>Space</kbd> / <kbd>Enter</kbd> | Start / pause |
| <kbd>←</kbd> / <kbd>→</kbd> | Switch mode (Focus / Short break / Long break) |
| <kbd>Ctrl</kbd>+<kbd>,</kbd> | Preferences |
| <kbd>Ctrl</kbd>+<kbd>Q</kbd> | Quit |

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
