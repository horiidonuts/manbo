#!/usr/bin/python3
"""Print the sound files Manbo actually uses (SOUNDS in manbo/sounds.py) that
exist in data/sounds/, so packages ship only those — not every sample lying
around in the folder. Reads the source without importing it (no GStreamer)."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
tree = ast.parse((ROOT / "manbo" / "sounds.py").read_text())
values = {}
for node in tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        try:
            values[node.targets[0].id] = ast.literal_eval(node.value)
        except ValueError:
            pass

for stem, _volume in values["SOUNDS"].values():
    for ext in values["EXTENSIONS"]:
        path = ROOT / "data" / "sounds" / f"{stem}{ext}"
        if path.is_file():
            print(path.relative_to(ROOT))
            break
