"""
Public API for the backend (Shabharish):

    from ai import generate_asset_set, regenerate_asset

    session = generate_asset_set("post-apocalyptic farming game", "painterly", provider_name="gemini",
                                 out_dir="outputs/abc123", on_update=callback)
    session.assets -> {"character": {"status","path","name","prompt"}, ...}
    regenerate_asset(session, "weapon")
"""
import io
import json
import os
import random
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from .prompts import ASSET_TYPES, build_final_prompt, expand_concept
from .providers import get_provider
from .styles import DEFAULT_STYLE, STYLES


@dataclass
class Session:
    concept: str
    style: str
    plan: dict
    out_dir: str
    provider: object
    seed: int
    hero_bytes: bytes | None = None
    assets: dict = field(default_factory=dict)


def _postprocess(asset_type, data):
    """Icons: remove background if rembg installed, then resize. Returns PNG bytes."""
    from PIL import Image
    if asset_type.startswith("icon"):
        try:
            from rembg import remove
            data = remove(data)
        except Exception:
            pass
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((256, 256))
    else:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _make(session, asset_type, use_reference=True):
    a = session.assets[asset_type]
    plan_asset = next(x for x in session.plan["assets"] if x["type"] == asset_type)
    ref = session.hero_bytes if (use_reference and session.provider.supports_reference
                                 and asset_type != "character") else None
    prompt = build_final_prompt(plan_asset, session.style, has_reference=ref is not None)
    a.update(status="generating", prompt=prompt)
    try:
        raw = session.provider.generate(prompt, reference=ref, seed=session.seed)
        data = _postprocess(asset_type, raw)
        path = os.path.join(session.out_dir, f"{asset_type}.png")
        with open(path, "wb") as f:
            f.write(data)
        if asset_type == "character" and session.hero_bytes is None:
            session.hero_bytes = data
        a.update(status="done", path=path, error=None)
    except Exception as e:
        a.update(status="error", error=str(e))
    return a


def generate_asset_set(concept, style=DEFAULT_STYLE, provider_name=None, out_dir="outputs/session",
                       on_update=None, seed=None):
    if style not in STYLES:
        style = DEFAULT_STYLE
    os.makedirs(out_dir, exist_ok=True)
    plan = expand_concept(concept, style)
    s = Session(concept, style, plan, out_dir, get_provider(provider_name),
                seed if seed is not None else random.randint(1, 2**31 - 1))
    for a in plan["assets"]:
        s.assets[a["type"]] = {"type": a["type"], "name": a["name"], "status": "pending", "path": None, "error": None}
    if on_update:
        on_update(s)

    # Step 2: hero = style anchor (must finish first)
    _make(s, "character")
    if on_update:
        on_update(s)
    if s.hero_bytes is None:  # hero failed: retry once, otherwise continue without a reference
        _make(s, "character")

    # Step 3: everything else in parallel, conditioned on the hero
    rest = [t for t in ASSET_TYPES if t != "character"]

    def work(t):
        _make(s, t)
        if on_update:
            on_update(s)

    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(work, rest))
    write_manifest(s)
    return s


def write_manifest(session):
    """manifest.json beside the images: enough to restore the set later (used by the demo cache)."""
    data = {
        "concept": session.concept, "style": session.style, "plan": session.plan,
        "assets": {t: {"name": a["name"], "status": a["status"],
                       "file": os.path.basename(a["path"]) if a.get("path") else None}
                   for t, a in session.assets.items()},
    }
    with open(os.path.join(session.out_dir, "manifest.json"), "w") as f:
        json.dump(data, f, indent=2)


def regenerate_asset(session, asset_type):
    """Same plan, hero reference and style; new sample. Regenerating the character re-anchors the style,
    so we keep the old hero as the anchor to protect consistency unless it never existed."""
    if session.provider is None:  # session was restored from the demo cache
        session.provider = get_provider()
    old_hero = session.hero_bytes
    if asset_type == "character":
        session.hero_bytes = None
    session.seed = random.randint(1, 2**31 - 1)
    _make(session, asset_type)
    if asset_type == "character" and session.hero_bytes is None:
        session.hero_bytes = old_hero
    return session.assets[asset_type]


def naive_baseline(concept, provider_name=None, out_dir="outputs/naive"):
    """For the before/after demo: the same concept, raw prompts, no style anchor, no reference."""
    os.makedirs(out_dir, exist_ok=True)
    provider = get_provider(provider_name)
    subjects = {"character": "a character", "environment": "an environment", "weapon": "a weapon",
                "icon_1": "a potion icon", "icon_2": "a key icon", "icon_3": "a resource icon"}
    paths = {}

    def one(t):
        data = _postprocess(t, provider.generate(f"{subjects[t]} for a game about {concept}"))
        p = os.path.join(out_dir, f"{t}.png")
        with open(p, "wb") as f:
            f.write(data)
        paths[t] = p

    with ThreadPoolExecutor(max_workers=6) as ex:
        list(ex.map(one, ASSET_TYPES))
    return paths


def contact_sheet(paths, out_path, title=""):
    """Single side-by-side image of all assets: the demo's money shot."""
    from PIL import Image, ImageDraw
    cell = 320
    tiles = [p for p in paths if p and os.path.exists(p)]
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell + 40), (24, 24, 28))
    ImageDraw.Draw(sheet).text((10, 12), title, fill=(255, 255, 255))
    for i, p in enumerate(tiles):
        im = Image.open(p).convert("RGBA")
        im.thumbnail((cell - 10, cell - 10))
        bg = Image.new("RGBA", im.size, (60, 60, 66, 255))
        bg.alpha_composite(im)
        sheet.paste(bg.convert("RGB"), ((i % cols) * cell + 5, 40 + (i // cols) * cell + 5))
    sheet.save(out_path)
    return out_path
