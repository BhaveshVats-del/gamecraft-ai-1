# AI Pipeline: Design

## Flow
```
concept + style_id
   │
   ▼  prompts.expand_concept          (GPT-4o-mini, JSON-schema enforced, validated, template fallback)
plan = {world_notes, assets[6]: type/name/subject-prompt}
   │
   ▼  pipeline._make("character")     hero = style anchor (retried once on failure)
   │
   ▼  5 assets in parallel (ThreadPool, 5 workers)
      prompt = subject + layout + STYLE DESCRIPTOR + PALETTE (+ "use attached image as style reference")
      provider.generate(prompt, reference=hero)
   │
   ▼  postprocess: icons -> optional rembg -> 256px; others -> max 1024px PNG
```

## Consistency levers (strongest first)
1. Reference image (hero) passed to every other asset.
2. Identical style descriptor + palette text in every prompt (style never comes from the LLM).
3. LLM plan reuses motifs/materials across the six subjects.
4. Fixed seed per session (honoured by providers that support it).

## Why subject-only prompts from the LLM
If the LLM writes style text per asset it drifts. Style lives in `styles.py` and is appended identically.

## Failure handling
- LLM fails / no key: template plan, pipeline still runs.
- One asset fails: it gets `status="error"`, others finish; `regenerate_asset` retries just that one.
- Provider calls retry 3x with backoff.

## Public API (for backend)
```python
from ai import generate_asset_set, regenerate_asset, list_styles, ASSET_TYPES

session = generate_asset_set(concept, style_id, provider_name=None,
                             out_dir="outputs/<session_id>", on_update=callback)
session.assets[type] == {"type","name","status": pending|generating|done|error, "path","error","prompt"}
regenerate_asset(session, "weapon")
```
Run `generate_asset_set` in a background thread/task; `on_update(session)` fires after each asset so the
status endpoint can report real progress. Keep the `session` object in memory keyed by session_id.

## Plan LLM (prompt expansion)
`PLAN_LLM=openai | gemini | none | auto` (default auto: OpenAI key, else Gemini key, else template fallback).
Models: `OPENAI_LLM_MODEL` (gpt-4o-mini), `GEMINI_LLM_MODEL` (gemini-2.5-flash). Output is validated either way.

## Demo reliability (cache)
```python
from ai import generate_or_cached
session, source = generate_or_cached(concept, style, out_dir=f"outputs/{sid}", on_update=cb)
# source: "cache" | "live" | "cache_fallback"
```
1. Night before: `python ai/scripts/pregenerate_demos.py --provider <real>` -> `demo_cache/<id>/`.
2. Demo day: `DEMO_MODE=1` serves cached sets instantly for the 5 demo concepts; any other concept runs live.
   With `DEMO_MODE=0`, live runs but falls back to the cache if the provider errors or exceeds `LIVE_TIMEOUT_S` (90s).
3. Only complete (6/6) sets are used. Tell the frontend `source` if you want a subtle "cached" badge, or ignore it.
Match is by demo id or exact concept text (case-insensitive), so the demo concepts must be typed or picked as written
in `data/demo_concepts.json`. Suggest Gizmo-01 add them as one-click example chips.

## Adding a style
Add an entry to `STYLES` in `styles.py` (label, descriptor, 6-colour palette). The frontend picks it up via `list_styles()`.
