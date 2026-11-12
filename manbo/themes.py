"""Pastel themes. Each theme has a palette per timer mode.

bg     -> window background
button -> top face of the big 3D button (its side/housing are derived)
text   -> labels, icons, and the tint used for shading
"""

THEMES = {
    "blossom": {
        "name": "Blossom",
        "modes": {
            "focus": {"bg": "#FFE5D9", "button": "#F4ACB7", "text": "#7E6770"},
            "short": {"bg": "#D8E2DC", "button": "#F4ACB7", "text": "#7E6770"},
            "long": {"bg": "#FFCAD4", "button": "#9D8189", "text": "#7E6770"},
        },
    },
    "cotton": {
        "name": "Cotton Candy",
        "modes": {
            "focus": {"bg": "#FFC8DD", "button": "#CDB4DB", "text": "#5E4B70"},
            "short": {"bg": "#BDE0FE", "button": "#FFAFCC", "text": "#5E4B70"},
            "long": {"bg": "#CDB4DB", "button": "#A2D2FF", "text": "#5E4B70"},
        },
    },
    "coastal": {
        "name": "Coastal",
        "modes": {
            "focus": {"bg": "#F8F4F1", "button": "#CEAAA1", "text": "#3B7DA1"},
            "short": {"bg": "#EAF0F2", "button": "#98B9CB", "text": "#3B7DA1"},
            "long": {"bg": "#F1EEE4", "button": "#3B7DA1", "text": "#3B7DA1"},
        },
    },
}

DEFAULT_THEME = "blossom"


def palette(theme, mode):
    return THEMES.get(theme, THEMES[DEFAULT_THEME])["modes"][mode]


# -- color helpers (rgb tuples in 0..1) ---------------------------------------

def hex_to_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


WHITE = (1.0, 1.0, 1.0)


def luminance(rgb):
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# -- CSS -----------------------------------------------------------------------

BASE_CSS = """
window.manbo {
  transition: background-color 450ms ease-out, color 450ms ease-out;
}
window.manbo headerbar.flat {
  background: none;
  box-shadow: none;
  color: inherit;
}
window.manbo headerbar button {
  color: inherit;
}
.time-label {
  font-size: 76px;
  font-weight: 800;
  font-feature-settings: "tnum";
  letter-spacing: -1px;
}
.dot {
  min-width: 10px;
  min-height: 10px;
  border-radius: 999px;
  background-color: alpha(currentColor, 0.18);
  transition: background-color 300ms ease-out;
}
.dot.filled {
  background-color: currentColor;
}
.round-action {
  min-width: 44px;
  min-height: 44px;
  color: inherit;
}
"""


def build_css():
    rules = [BASE_CSS]
    for key, theme in THEMES.items():
        for mode, pal in theme["modes"].items():
            rules.append(
                f"window.manbo.theme-{key}.mode-{mode} "
                f"{{ background-color: {pal['bg']}; color: {pal['text']}; }}"
            )
    return "\n".join(rules)
