# gamecraft-ai
AI-powered game asset generator for Banana Hacks 2026

One game idea in → a consistent set of 6 game assets out (character, environment,
weapon, 3 inventory icons), all anchored to the same art style.

## Run it
```bash
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/pip install -r ai/requirements.txt
.venv/bin/python backend/app.py        # → http://localhost:8000
```

## AI model (provider)
The backend auto-picks the first available image model from the environment,
falling back to the offline mock (no keys needed):

| Env var | Enables |
|---|---|
| `GEMINI_API_KEY` | Gemini (`gemini-2.5-flash-image`) |
| `OPENAI_API_KEY` | OpenAI (`gpt-image-1`) |
| `REPLICATE_API_TOKEN` | Replicate (FLUX / SDXL) |
| `IMAGE_PROVIDER` | Force one of `mock \| openai \| gemini \| replicate` |

See `ai/.env.example` for all knobs (LLM plan model, demo cache, timeouts).

## Layout
- `ai/` — the pipeline: LLM concept plan → hero style anchor → 6 parallel assets,
  pluggable providers, demo cache with live-timeout fallback
- `backend/app.py` — Flask REST API wiring the frontend to `ai/`
  (`/api/generate`, `/api/status/<id>`, `/api/regenerate/<id>/<asset>`,
  `/api/assets/<id>/<file>`, `/api/export/<id>`)
- `frontend/index.html` — demo UI
- Test the pipeline offline: `pytest ai/tests -q` and
  `python ai/scripts/run_test.py --provider mock`
