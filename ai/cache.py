"""
Demo reliability layer.

  pregenerate_demos()   run once before the demo: builds + stores full sets for data/demo_concepts.json
  generate_or_cached()  what the backend calls in the demo: cached set instantly, or live with a safety net

Env:
  GAMECRAFT_CACHE_DIR   default "demo_cache"
  DEMO_MODE=1           serve cached sets first (instant), live only if no cache entry exists
  LIVE_TIMEOUT_S        default 90; live run slower than this -> fall back to the cache if one exists
"""
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutTimeout

from .pipeline import Session, generate_asset_set, write_manifest
from .prompts import ASSET_TYPES

DEMOS_PATH = os.path.join(os.path.dirname(__file__), "data", "demo_concepts.json")


def cache_dir():
    return os.getenv("GAMECRAFT_CACHE_DIR", "demo_cache")


def _norm(s):
    return " ".join(s.lower().split())


def load_demos():
    return json.load(open(DEMOS_PATH))


def pregenerate_demos(provider_name=None, root=None, ids=None, on_progress=None):
    """Generate and store a full set per demo concept. Returns {demo_id: done_count}."""
    root = root or cache_dir()
    result = {}
    for d in load_demos():
        if ids and d["id"] not in ids:
            continue
        out = os.path.join(root, d["id"])
        s = generate_asset_set(d["concept"], d["style"], provider_name, out_dir=out)
        done = sum(a["status"] == "done" for a in s.assets.values())
        result[d["id"]] = done
        if on_progress:
            on_progress(d["id"], done)
    return result


def find_cached(key, style=None, root=None):
    """key = demo id OR the exact concept text (case/space-insensitive). Returns entry dir or None.
    Only complete sets (6/6 done) count."""
    root = root or cache_dir()
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root)):
        mpath = os.path.join(root, name, "manifest.json")
        if not os.path.exists(mpath):
            continue
        with open(mpath) as f:
            m = json.load(f)
        if not all(m["assets"].get(t, {}).get("status") == "done" for t in ASSET_TYPES):
            continue
        by_id = key == name
        by_text = _norm(key) == _norm(m["concept"]) and (style is None or style == m["style"])
        if by_id or by_text:
            return os.path.join(root, name)
    return None


def load_cached_set(entry_dir, out_dir):
    """Copy a cached set into out_dir and return a Session shaped like a live one (provider loads lazily)."""
    with open(os.path.join(entry_dir, "manifest.json")) as f:
        m = json.load(f)
    os.makedirs(out_dir, exist_ok=True)
    s = Session(m["concept"], m["style"], m["plan"], out_dir, None, 0)
    for t in ASSET_TYPES:
        info = m["assets"][t]
        dst = os.path.join(out_dir, info["file"])
        shutil.copyfile(os.path.join(entry_dir, info["file"]), dst)
        s.assets[t] = {"type": t, "name": info["name"], "status": "done", "path": dst, "error": None}
    with open(s.assets["character"]["path"], "rb") as f:
        s.hero_bytes = f.read()
    write_manifest(s)
    return s


def generate_or_cached(concept, style, provider_name=None, out_dir="outputs/session", on_update=None,
                       root=None, prefer_cache=None, timeout_s=None):
    """Drop-in for generate_asset_set with a demo safety net. Returns (session, source) where
    source is 'cache', 'live' or 'cache_fallback'."""
    root = root or cache_dir()
    if prefer_cache is None:
        prefer_cache = os.getenv("DEMO_MODE", "0") == "1"
    if timeout_s is None:
        timeout_s = float(os.getenv("LIVE_TIMEOUT_S", "90"))
    hit = find_cached(concept, style, root)

    if hit and prefer_cache:
        s = load_cached_set(hit, out_dir)
        if on_update:
            on_update(s)
        return s, "cache"

    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(generate_asset_set, concept, style, provider_name, out_dir, on_update)
    try:
        s = fut.result(timeout=timeout_s)
        if hit and not all(a["status"] == "done" for a in s.assets.values()):
            raise RuntimeError("live set incomplete")
        return s, "live"
    except (FutTimeout, Exception):
        if not hit:
            raise
        s = load_cached_set(hit, out_dir + "_cached")
        if on_update:
            on_update(s)
        return s, "cache_fallback"
    finally:
        ex.shutdown(wait=False)
