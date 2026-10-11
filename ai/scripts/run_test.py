"""
Run from the REPO ROOT:
  python ai/scripts/run_test.py --provider mock
  python ai/scripts/run_test.py --provider gemini --demo farm_cyberpunk --compare
  python ai/scripts/run_test.py --provider openai --all-demos
Outputs: outputs/<provider>_<style>_<id>/{*.png, contact_sheet.png, naive_sheet.png}
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ai import (ASSET_TYPES, contact_sheet, generate_asset_set,  # noqa: E402
                         naive_baseline, regenerate_asset)

HERE = os.path.dirname(os.path.abspath(__file__))
DEMOS = json.load(open(os.path.join(HERE, "..", "data", "demo_concepts.json")))


def run(provider, concept, style, tag, compare):
    out = f"outputs/{provider}_{style}_{tag}"
    t0 = time.time()
    s = generate_asset_set(concept, style, provider, out_dir=out)
    dt = time.time() - t0
    ok = sum(1 for a in s.assets.values() if a["status"] == "done")
    print(f"[{tag}] {ok}/6 assets in {dt:.1f}s -> {out}")
    for k, v in s.assets.items():
        if v["status"] != "done":
            print("   FAILED", k, v.get("error"))
    contact_sheet([s.assets[t]["path"] for t in ASSET_TYPES], f"{out}/contact_sheet.png",
                  f"CONSISTENT [{style}]: {concept}")
    regenerate_asset(s, "weapon")
    print("   regenerate weapon:", s.assets["weapon"]["status"])
    if compare:
        n = naive_baseline(concept, provider, f"{out}/naive")
        contact_sheet([n[t] for t in ASSET_TYPES], f"{out}/naive_sheet.png", f"NAIVE: {concept}")
        print("   naive sheet written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default=os.getenv("IMAGE_PROVIDER", "mock"))
    ap.add_argument("--demo", default="farm_cyberpunk", help="id from data/demo_concepts.json")
    ap.add_argument("--concept")
    ap.add_argument("--style", default="painterly")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--all-demos", action="store_true")
    a = ap.parse_args()
    if a.concept:
        run(a.provider, a.concept, a.style, "custom", a.compare)
    else:
        for d in (DEMOS if a.all_demos else [x for x in DEMOS if x["id"] == a.demo]):
            run(a.provider, d["concept"], d["style"], d["id"], a.compare)
