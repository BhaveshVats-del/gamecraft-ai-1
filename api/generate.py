"""Vercel serverless handler: POST /api/generate.

Runs the ai/ pipeline synchronously (Vercel has no background threads or
persistent disk) and returns the finished set inline as data URLs.

Mock provider: instant. Real providers (GEMINI_API_KEY / OPENAI_API_KEY):
~30-90 s for the full set - needs a plan with a long enough function
duration (Vercel Pro allows up to 300 s).
"""
import base64
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai import ASSET_TYPES, DEFAULT_STYLE, STYLES, default_provider_name, generate_asset_set  # noqa: E402


def handler(req, res):
    if req.method != "POST":
        return res.status(405).json({"error": "POST only"})
    try:
        body = json.loads(req.body or b"{}")
    except json.JSONDecodeError:
        return res.status(400).json({"error": "invalid JSON body"})

    concept = (body.get("concept") or "").strip()
    if not concept:
        return res.status(400).json({"error": "concept is required"})
    style = body.get("style") or DEFAULT_STYLE
    if style not in STYLES:
        style = DEFAULT_STYLE

    provider = default_provider_name()
    try:
        with tempfile.TemporaryDirectory() as out:
            session = generate_asset_set(concept, style, provider, out_dir=out)
            assets = []
            for t in ASSET_TYPES:
                a = session.assets[t]
                item = {"type": t, "name": a["name"], "status": a["status"],
                        "error": a["error"]}
                if a["status"] == "done" and a.get("path"):
                    with open(a["path"], "rb") as f:
                        item["data_url"] = "data:image/png;base64," + base64.b64encode(f.read()).decode()
                assets.append(item)
    except Exception as exc:  # noqa: BLE001
        return res.status(500).json({"error": f"{type(exc).__name__}: {exc}"})

    done = sum(1 for a in assets if a["status"] == "done")
    return res.status(200).json({"provider": provider, "style": style,
                                 "concept": concept, "source": "live",
                                 "done": done, "total": len(assets),
                                 "assets": assets})
