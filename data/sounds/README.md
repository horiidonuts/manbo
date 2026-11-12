# Sounds

The sound files themselves are **not included** in the repository (their
license doesn't allow redistribution). Put your own files here with the names
below — without them the clicks are silent and the chime falls back to the
system sound.

Sound effects used by Manbo. Which file plays for which event is set in
`SOUNDS` in [`manbo/sounds.py`](../../manbo/sounds.py) (file name without
extension + volume):

| Event | File | Plays when | If missing |
| --- | --- | --- | --- |
| `press` | `button_press` | the button sinks (start) | silent |
| `pop` | `button_pop_up` | the button pops up (time over, pause, reset, mode switch) | silent |
| `chime` | `chime1` | a session ends | system `complete.oga` chime |

Supported extensions: `.ogg`, `.oga`, `.opus`, `.wav`, `.flac`, `.mp3`.
Short, trimmed files (no leading silence) feel the snappiest.
