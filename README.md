# gamecraft-ai

AI-powered game asset generator for Banana Hacks 2026 — built on Google Gemini 2.5 Flash Image (aka **nano-banana** 🍌).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r ai/requirements.txt
```

Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey), then save it:

```bash
echo "GEMINI_API_KEY=your_key_here" > ai/.env
```

(`.env` is gitignored — your key stays local. Alternatively: `export GEMINI_API_KEY=...`)

## Usage

```bash
# Generate a sprite (default asset type)
python ai/generate.py "a fire-breathing dragon boss"

# Pick an asset preset and art style
python ai/generate.py "health potion" --type icon --style "cartoon, vibrant"
python ai/generate.py "slime enemy" --type character --style pixel art

# Game-ready sprite with a transparent background
python ai/generate.py "space marine" --cutout

# 3 variations at once
python ai/generate.py "treasure chest" --count 3

# Seamless tileable texture / wide background
python ai/generate.py "grass field" --type texture
python ai/generate.py "haunted forest at dusk" --type background --aspect 16:9

# Edit an existing image with a text instruction
python ai/generate.py "make the armor golden" --edit ai/outputs/dragon.png
```

### Asset types

| `--type` | Use for |
|-----------|---------|
| `sprite` *(default)* | Characters/objects, full-body, centered |
| `character` | Front-facing character art |
| `item` | Pickups, props, loot |
| `icon` | Inventory/UI icons, readable when small |
| `texture` | Seamless tileable surfaces |
| `background` | Parallax-ready environments |
| `ui` | Buttons, panels, HUD elements |
| `raw` | No prompt engineering — your prompt, verbatim |

Images are saved to `ai/outputs/` as timestamped PNGs.

### Options

```
-t, --type     asset preset (see table above)      default: sprite
-s, --style    freeform art style                  e.g. "pixel art"
-a, --aspect   1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9   default: 1:1
-n, --count    number of variations                default: 1
-o, --out      output file or directory            default: ai/outputs
-e, --edit     edit existing image(s) instead      e.g. --edit img.png
--cutout       generate on solid magenta, then key it out to transparency
--model        override model id                   default: gemini-2.5-flash-image
```
