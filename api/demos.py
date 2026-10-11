"""Vercel serverless handler: GET /api/demos.

forest_spirits ships pre-generated REAL AI art as static files in /demo/,
so on Vercel that chip is served instantly with no function call at all.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.cache import load_demos  # noqa: E402

_STATIC = {
    "forest_spirits": {
        "static": True,
        "base": "/demo/forest_spirits",
        "names": {
            "character": "Aelwyn, the Druid Hero",
            "environment": "The Whispering Clearing",
            "weapon": "Spirit-Glow Staff",
            "icon_1": "Glowroot Potion",
            "icon_2": "Mossbound Key",
            "icon_3": "Spirit Crystals",
        },
    },
}


def handler(req, res):
    demos = load_demos()
    for d in demos:
        d.update(_STATIC.get(d["id"], {}))
    return res.status(200).json({"demos": demos})
