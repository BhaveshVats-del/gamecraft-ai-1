"""Style presets. Pure data: the frontend can list them via list_styles()."""

STYLES = {
    "pixel_art": {
        "label": "Pixel Art",
        "descriptor": "16-bit pixel art, crisp hard pixel edges, limited color palette, "
                      "no anti-aliasing, flat shading, retro SNES-era game asset",
        "palette": ["#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75", "#38b764"],
    },
    "painterly": {
        "label": "Hand-Painted Fantasy",
        "descriptor": "hand-painted digital illustration, soft brush strokes, warm rich colors, "
                      "visible painterly texture, storybook fantasy game art",
        "palette": ["#2b1d2f", "#7a3b3b", "#c9803a", "#e8c170", "#5f8a5a", "#3b5b7a"],
    },
    "scifi_neon": {
        "label": "Neon Sci-Fi",
        "descriptor": "futuristic neon sci-fi concept art, dark background tones, glowing cyan and "
                      "magenta accents, sleek hard-surface design, high contrast lighting",
        "palette": ["#0b0c1e", "#1f2a5a", "#00e5ff", "#ff2bd6", "#9b5cff", "#e8f1ff"],
    },
}

DEFAULT_STYLE = "painterly"


def list_styles():
    return [{"id": k, "label": v["label"], "palette": v["palette"]} for k, v in STYLES.items()]
