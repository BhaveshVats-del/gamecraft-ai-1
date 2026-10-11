# ai: GameCraft AI (AI layer)

Turns a game concept + art style into a **consistent set of 6 game assets**
(character, environment, weapon, 3 inventory icons).

## Setup
```bash
pip install -r ai/requirements.txt
cp ai/.env.example .env      # fill in the key(s) you use
```

## Quick start
```bash
pytest ai/tests -q                                   # offline, no keys needed
python ai/scripts/run_test.py --provider mock        # smoke test
python ai/scripts/run_test.py --provider gemini --demo farm_cyberpunk --compare
python ai/scripts/pregenerate_demos.py --provider gemini   # demo backup cache
```
Results: `outputs/<provider>_<style>_<id>/contact_sheet.png` (consistent) and `naive_sheet.png` (before/after).

## Use from the backend
```python
from ai import generate_asset_set, regenerate_asset, list_styles
```
See `docs/PIPELINE.md` for the full contract.

## Layout
```
ai/
├── __init__.py        public exports
├── styles.py          3 style presets
├── prompts.py         LLM expansion, schema, validation, fallback, final prompt builder
├── providers.py       mock / openai / gemini / replicate
├── pipeline.py        generate_asset_set, regenerate_asset, naive_baseline, contact_sheet
├── cache.py           pregenerate_demos, generate_or_cached (demo safety net)
├── data/demo_concepts.json
├── docs/PIPELINE.md   design + API
├── docs/TEST_REPORT.md  fill in after real-model tests
├── scripts/run_test.py
├── scripts/pregenerate_demos.py
└── tests/test_pipeline.py
```

## Owner
Husnain: AI pipeline.
