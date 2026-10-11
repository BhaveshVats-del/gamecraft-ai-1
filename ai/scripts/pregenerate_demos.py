"""
Build the demo backup cache (run once, ideally the night before, with the REAL provider):
  python ai/scripts/pregenerate_demos.py --provider gemini
  python ai/scripts/pregenerate_demos.py --provider gemini --ids farm_cyberpunk pirate_cats
Result: demo_cache/<id>/{6 pngs, manifest.json}. Commit it to the repo or keep it on the demo machine.
Then run the backend with DEMO_MODE=1 for instant results, or leave it off for live-with-fallback.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ai import pregenerate_demos  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--provider", default=os.getenv("IMAGE_PROVIDER", "mock"))
ap.add_argument("--root", default=None)
ap.add_argument("--ids", nargs="*")
a = ap.parse_args()
res = pregenerate_demos(a.provider, a.root, a.ids, lambda i, n: print(f"{i}: {n}/6 done"))
bad = {k: v for k, v in res.items() if v < 6}
print("ALL COMPLETE" if not bad else f"INCOMPLETE (re-run these): {bad}")
