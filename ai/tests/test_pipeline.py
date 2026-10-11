"""Offline tests (mock provider). Run from repo root:  pytest ai/tests -q"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
for _k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
    os.environ.pop(_k, None)  # force the no-LLM fallback plan
os.environ["PLAN_LLM"] = "none"

from ai import (ASSET_TYPES, STYLES, contact_sheet, generate_asset_set,  # noqa: E402
                         list_styles, naive_baseline, regenerate_asset)
from ai import pipeline as pl  # noqa: E402
from ai.prompts import (build_final_prompt, fallback_plan,  # noqa: E402
                                 validate_plan)
from ai.providers import ImageProvider, MockProvider, get_provider  # noqa: E402


def test_styles_listed():
    ids = {s["id"] for s in list_styles()}
    assert {"pixel_art", "painterly", "scifi_neon"} <= ids
    assert all(len(s["palette"]) >= 4 for s in STYLES.values())


def test_fallback_plan_valid():
    plan = validate_plan(fallback_plan("a game about frogs"))
    assert [a["type"] for a in plan["assets"]] == ASSET_TYPES


def test_validate_plan_rejects_missing():
    plan = fallback_plan("x")
    plan["assets"] = plan["assets"][:3]
    with pytest.raises(ValueError):
        validate_plan(plan)


def test_prompt_contains_style_and_reference_wording():
    a = fallback_plan("x")["assets"][2]
    p = build_final_prompt(a, "pixel_art", has_reference=True)
    assert STYLES["pixel_art"]["descriptor"] in p
    assert "attached image" in p
    assert "attached image" not in build_final_prompt(a, "pixel_art", has_reference=False)


def test_full_generation(tmp_path):
    updates = []
    s = generate_asset_set("a game about frogs", "painterly", "mock", str(tmp_path),
                           on_update=lambda s: updates.append(1))
    assert set(s.assets) == set(ASSET_TYPES)
    assert all(a["status"] == "done" and os.path.exists(a["path"]) for a in s.assets.values())
    assert s.hero_bytes and updates


def test_unknown_style_falls_back(tmp_path):
    s = generate_asset_set("x", "does_not_exist", "mock", str(tmp_path))
    assert s.style == "painterly"


def test_regenerate_keeps_hero(tmp_path):
    s = generate_asset_set("x", "scifi_neon", "mock", str(tmp_path))
    hero = s.hero_bytes
    assert regenerate_asset(s, "weapon")["status"] == "done"
    assert s.hero_bytes == hero


class FailingProvider(MockProvider):
    def generate(self, prompt, reference=None, seed=None):
        if "weapon" in prompt.lower():
            raise RuntimeError("boom")
        return super().generate(prompt, reference, seed)


def test_one_failure_does_not_kill_set(tmp_path, monkeypatch):
    monkeypatch.setattr(pl, "get_provider", lambda name=None: FailingProvider())
    s = generate_asset_set("x", "painterly", "mock", str(tmp_path))
    assert s.assets["weapon"]["status"] == "error"
    assert "boom" in s.assets["weapon"]["error"]
    assert sum(a["status"] == "done" for a in s.assets.values()) == 5


def test_baseline_and_sheet(tmp_path):
    paths = naive_baseline("frogs", "mock", str(tmp_path / "n"))
    out = contact_sheet([paths[t] for t in ASSET_TYPES], str(tmp_path / "sheet.png"), "t")
    assert os.path.exists(out)


def test_get_provider_mock():
    assert isinstance(get_provider("mock"), ImageProvider)


# ---------- plan LLM selection / parsing ----------
def test_parse_plan_text_handles_fences():
    from ai.prompts import parse_plan_text
    import json
    raw = "```json\n" + json.dumps(fallback_plan("x")) + "\n```"
    assert [a["type"] for a in parse_plan_text(raw)["assets"]] == ASSET_TYPES


def test_pick_plan_llm(monkeypatch):
    from ai.prompts import pick_plan_llm
    monkeypatch.setenv("PLAN_LLM", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert pick_plan_llm() == "none"
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    assert pick_plan_llm() == "gemini"
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert pick_plan_llm() == "openai"
    monkeypatch.setenv("PLAN_LLM", "gemini")
    assert pick_plan_llm() == "gemini"


# ---------- demo cache ----------
def _prime_cache(root):
    from ai import pregenerate_demos
    return pregenerate_demos("mock", str(root), ids=["pirate_cats"])


def test_pregenerate_and_find(tmp_path):
    assert _prime_cache(tmp_path) == {"pirate_cats": 6}
    from ai import find_cached
    from ai.cache import load_demos
    d = next(x for x in load_demos() if x["id"] == "pirate_cats")
    assert find_cached("pirate_cats", None, str(tmp_path))
    assert find_cached(d["concept"].upper(), d["style"], str(tmp_path))
    assert find_cached("unknown concept", None, str(tmp_path)) is None


def test_prefer_cache_skips_live(tmp_path, monkeypatch):
    _prime_cache(tmp_path / "c")
    from ai import generate_or_cached
    from ai.cache import load_demos
    monkeypatch.setattr(pl, "get_provider", lambda name=None: (_ for _ in ()).throw(AssertionError("live called")))
    d = next(x for x in load_demos() if x["id"] == "pirate_cats")
    s, src = generate_or_cached(d["concept"], d["style"], "mock", str(tmp_path / "o"),
                                root=str(tmp_path / "c"), prefer_cache=True)
    assert src == "cache" and all(a["status"] == "done" for a in s.assets.values())


def test_live_failure_falls_back_to_cache(tmp_path, monkeypatch):
    _prime_cache(tmp_path / "c")
    from ai import generate_or_cached
    from ai.cache import load_demos

    class Dead(MockProvider):
        def generate(self, prompt, reference=None, seed=None):
            raise RuntimeError("api down")
    monkeypatch.setattr(pl, "get_provider", lambda name=None: Dead())
    d = next(x for x in load_demos() if x["id"] == "pirate_cats")
    s, src = generate_or_cached(d["concept"], d["style"], "mock", str(tmp_path / "o"),
                                root=str(tmp_path / "c"), prefer_cache=False)
    assert src == "cache_fallback"


def test_live_timeout_falls_back_to_cache(tmp_path, monkeypatch):
    _prime_cache(tmp_path / "c")
    import time
    from ai import generate_or_cached
    from ai.cache import load_demos

    class Slow(MockProvider):
        def generate(self, prompt, reference=None, seed=None):
            time.sleep(2)
            return super().generate(prompt, reference, seed)
    monkeypatch.setattr(pl, "get_provider", lambda name=None: Slow())
    d = next(x for x in load_demos() if x["id"] == "pirate_cats")
    s, src = generate_or_cached(d["concept"], d["style"], "mock", str(tmp_path / "o"),
                                root=str(tmp_path / "c"), prefer_cache=False, timeout_s=0.3)
    assert src == "cache_fallback"


def test_no_cache_and_live_ok_is_live(tmp_path):
    from ai import generate_or_cached
    s, src = generate_or_cached("brand new idea", "painterly", "mock", str(tmp_path / "o"),
                                root=str(tmp_path / "none"), prefer_cache=False)
    assert src == "live"


def test_regenerate_on_cached_session(tmp_path):
    _prime_cache(tmp_path / "c")
    from ai import find_cached, load_cached_set
    s = load_cached_set(find_cached("pirate_cats", None, str(tmp_path / "c")), str(tmp_path / "o"))
    assert s.provider is None
    assert regenerate_asset(s, "weapon")["status"] == "done"
    #-
