#!/usr/bin/env python3
"""GameCraft AI — game asset image generation via Google Gemini (nano-banana).

Turns a text prompt into ready-to-use game assets (sprites, icons, textures,
backgrounds...) using the Gemini 2.5 Flash Image model.

Setup:
    1. pip install -r ai/requirements.txt
    2. Get an API key at https://aistudio.google.com/apikey
    3. Put it in ai/.env  ->  GEMINI_API_KEY=your_key_here
       (or: export GEMINI_API_KEY=your_key_here)

Usage:
    python ai/generate.py "a fire-breathing dragon boss"
    python ai/generate.py "health potion" --type icon --style "cartoon, vibrant"
    python ai/generate.py "slime enemy" --cutout --count 3
    python ai/generate.py "grass field tile" --type texture --aspect 1:1
    python ai/generate.py "make the armor golden" --edit outputs/dragon.png

Images are saved to ai/outputs/ by default.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTDIR = Path(__file__).resolve().parent / "outputs"
DEFAULT_MODEL = "gemini-2.5-flash-image"  # "nano banana"
SUPPORTED_ASPECTS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]

# Prompt presets that steer the model toward usable game assets.
ASSET_TYPES = {
    "sprite": (
        "a single {subject}, full body centered in frame, 2D game sprite art, "
        "clean solid background, crisp edges, no text, no watermark, no border"
    ),
    "character": (
        "a single game character: {subject}, full body, front-facing, centered, "
        "2D game art style, clean solid background, expressive, no text, no watermark"
    ),
    "item": (
        "a single game item: {subject}, centered, 2D game art style, clean solid "
        "background, vibrant colors, no text, no watermark"
    ),
    "icon": (
        "a game inventory icon of {subject}, centered, simple bold shapes, readable "
        "at small sizes, 2D game art style, clean solid background, no text, no watermark"
    ),
    "texture": (
        "a seamless tileable game texture of {subject}, flat even lighting, uniform, "
        "edge-to-edge pattern, no borders, no text, no watermark"
    ),
    "background": (
        "a 2D game environment background of {subject}, wide scene, parallax-ready, "
        "consistent lighting, no characters, no text, no watermark"
    ),
    "ui": (
        "a game UI element: {subject}, clean vector-like 2D game art, centered, "
        "solid background, no text, no watermark"
    ),
    "raw": "{subject}",  # no prompt engineering, use the prompt as-is
}


# --------------------------------------------------------------------------
# API key handling
# --------------------------------------------------------------------------

def load_api_key() -> str:
    """Read the Gemini API key from the environment or a nearby .env file."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key.strip()

    for candidate in (Path(__file__).resolve().parent / ".env", REPO_ROOT / ".env"):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith(("GEMINI_API_KEY=", "GOOGLE_API_KEY=")):
                    value = line.split("=", 1)[1].strip().strip("'\"")
                    if value:
                        return value

    sys.exit(
        "\nERROR: No Gemini API key found.\n"
        "  1. Get a free key at https://aistudio.google.com/apikey\n"
        "  2. Save it in ai/.env as:  GEMINI_API_KEY=your_key_here\n"
        "     (or run:  export GEMINI_API_KEY=your_key_here)\n"
    )


def get_client():
    try:
        from google import genai
    except ImportError:
        sys.exit(
            "\nERROR: The google-genai package is not installed.\n"
            "Run:  pip install -r ai/requirements.txt\n"
        )
    return genai.Client(api_key=load_api_key())


# --------------------------------------------------------------------------
# Prompt building
# --------------------------------------------------------------------------

def build_prompt(subject: str, asset_type: str, style: str | None, cutout: bool) -> str:
    prompt = ASSET_TYPES[asset_type].format(subject=subject.strip())
    if style:
        prompt += f". Art style: {style.strip()}"
    if cutout:
        prompt += (
            ". Place the subject on a completely solid flat pure magenta background "
            "(#FF00FF), with no shadows, gradients or highlights on the background, "
            "and the subject must not touch the image edges"
        )
    return prompt


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-") or "asset"


def output_path(outdir: Path, subject: str, index: int, total: int) -> Path:
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{slugify(subject)}"
    if total > 1:
        name += f"-{index + 1:02d}"
    return outdir / f"{name}.png"


# --------------------------------------------------------------------------
# Background removal (for --cutout)
# --------------------------------------------------------------------------

def remove_background(img, tolerance: int = 90, feather: int = 60):
    """Make the flat background color transparent.

    Assumes the model followed instructions and used a solid background
    (magenta when --cutout is used). Samples the four corners to find it.
    Pixels within `tolerance` of the background become fully transparent;
    pixels between `tolerance` and `tolerance + feather` get partial alpha,
    which softens anti-aliased edges and reduces color halos.
    """
    img = img.convert("RGBA")
    width, height = img.size
    pixels = img.load()
    corners = [
        pixels[0, 0][:3],
        pixels[width - 1, 0][:3],
        pixels[0, height - 1][:3],
        pixels[width - 1, height - 1][:3],
    ]
    bg = max(set(corners), key=corners.count)  # most common corner color
    upper = tolerance + feather
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            dist = abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])
            if dist <= tolerance:
                pixels[x, y] = (r, g, b, 0)
            elif dist < upper:
                alpha = int(255 * (dist - tolerance) / feather)
                pixels[x, y] = (r, g, b, min(a, alpha))
    return img


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def generate_image(client, model: str, prompt: str, aspect: str, input_images: list):
    """Call Gemini and return the raw PNG bytes (raises RuntimeError on refusal)."""
    from google.genai import types

    contents: list = []
    for path in input_images:  # edit mode
        contents.append(load_input_image(path))
    contents.append(prompt)

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["Image"],
            image_config=types.ImageConfig(aspect_ratio=aspect),
        ),
    )

    try:
        parts = response.candidates[0].content.parts
    except (AttributeError, IndexError):
        parts = []

    image_data = next(
        (p.inline_data.data for p in parts if p.inline_data is not None), None
    )
    if image_data:
        return image_data

    text = " ".join(p.text for p in parts if getattr(p, "text", None)).strip()
    finish = getattr(response.candidates[0], "finish_reason", "UNKNOWN") if response.candidates else "NO_CANDIDATE"
    raise RuntimeError(f"Model returned no image (finish_reason={finish}). {text}".strip())


def load_input_image(path: str):
    """Load a local image file as a Gemini Part (for --edit mode)."""
    from google.genai import types

    path = Path(path)
    if not path.is_file():
        sys.exit(f"\nERROR: Input image not found: {path}\n")
    suffix = path.suffix.lstrip(".").lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(suffix)
    if mime is None:
        sys.exit(f"\nERROR: Unsupported image type '{path.suffix}' (use png/jpg/webp/gif).\n")
    return types.Part.from_bytes(data=path.read_bytes(), mime_type=mime)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="gamecraft-ai",
        description="Generate game assets with Gemini 2.5 Flash Image (nano banana).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  python ai/generate.py "a fire-breathing dragon boss"\n'
            '  python ai/generate.py "health potion" --type icon --style "cartoon, vibrant"\n'
            '  python ai/generate.py "slime enemy" --cutout --count 3\n'
            '  python ai/generate.py "grass field" --type texture --aspect 1:1\n'
            '  python ai/generate.py "make the armor golden" --edit outputs/dragon.png\n'
        ),
    )
    parser.add_argument("prompt", help="what to generate (or the edit instruction, with --edit)")
    parser.add_argument("-t", "--type", choices=list(ASSET_TYPES), default="sprite",
                        help="asset preset that shapes the prompt (default: sprite)")
    parser.add_argument("-s", "--style", default=None,
                        help='freeform art style, e.g. "pixel art" or "dark fantasy"')
    parser.add_argument("-a", "--aspect", default="1:1", choices=SUPPORTED_ASPECTS,
                        help="aspect ratio (default: 1:1)")
    parser.add_argument("-n", "--count", type=int, default=1, help="number of variations")
    parser.add_argument("-o", "--out", default=None,
                        help="output file (single image) or directory (default: ai/outputs)")
    parser.add_argument("-e", "--edit", nargs="*", default=None, metavar="IMG",
                        help="edit existing image(s) instead of generating from scratch")
    parser.add_argument("--cutout", action="store_true",
                        help="generate on a solid background, then make it transparent")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (default: {DEFAULT_MODEL})")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.prompt.strip():
        print("ERROR: Prompt cannot be empty.", file=sys.stderr)
        return 2
    if args.count < 1:
        print("ERROR: --count must be at least 1.", file=sys.stderr)
        return 2

    client = get_client()
    input_images = args.edit or []
    mode = "edit" if input_images else "generate"
    prompt = args.prompt.strip() if mode == "edit" else build_prompt(args.prompt, args.type, args.style, args.cutout)

    # Resolve output destination.
    if args.out:
        out = Path(args.out)
        if args.count > 1 and out.suffix:
            print("ERROR: --out must be a directory when --count > 1.", file=sys.stderr)
            return 2
        outdir = out if out.suffix == "" else out.parent
        outdir.mkdir(parents=True, exist_ok=True)
        fixed_name = out if out.suffix and args.count == 1 else None
    else:
        outdir = DEFAULT_OUTDIR
        outdir.mkdir(parents=True, exist_ok=True)
        fixed_name = None

    print(f"GameCraft AI  [{mode}]  model={args.model}  aspect={args.aspect}")
    print(f"Prompt: {prompt}\n")

    for i in range(args.count):
        target = fixed_name or output_path(outdir, args.prompt, i, args.count)
        try:
            data = generate_image(client, args.model, prompt, args.aspect, input_images)
        except RuntimeError as exc:
            print(f"[{i + 1}/{args.count}] FAILED: {exc}", file=sys.stderr)
            continue
        except Exception as exc:  # network / auth / quota errors
            print(f"[{i + 1}/{args.count}] API error: {exc}", file=sys.stderr)
            return 1

        if args.cutout:
            from PIL import Image
            img = remove_background(Image.open(io.BytesIO(data)))
            img.save(target)
        else:
            Path(target).write_bytes(data)

        print(f"[{i + 1}/{args.count}] Saved -> {target}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
