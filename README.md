# gamecraft-ai
AI-powered game asset generator for Banana Hacks 2026

One game idea in → a consistent set of 6 game assets out (character, environment,
weapon, 3 inventory icons), all anchored to the same art style.

## Deploy on Vercel
1. [Vercel](https://vercel.com/) → **Add New → Project** → import this repo
   (`BhaveshVats-del/gamecraft-ai-1`).
2. Branch: `arena/af9b4220-gamecraft-ai-1` (or merge the open PR into `main`
   first and import the default branch). Framework: **Other** (Python is auto-detected
   from `api/` + `requirements.txt`).
3. *(Optional)* Environment Variables for a real image model:
   `GEMINI_API_KEY` and/or `OPENAI_API_KEY` (or force one with `IMAGE_PROVIDER`).
   The "forest spirits" demo chip works with **no keys** — its real AI art ships
   as static files in `demo/`.
4. **Deploy.** Done — the UI + `/api/*` serverless functions go live.

> Plan note: real-model generation takes ~30–90 s per set. Vercel Hobby's default
> function duration may cut that short — on Pro, raise Max Duration to 300 s.
> Without keys (or if a call times out), the mock provider keeps the app working.

## Run it locally
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DEMO_MODE=1 .venv/bin/python backend/app.py        # → http://localhost:8000
```
`DEMO_MODE=1` serves the pre-built AI demo set instantly (demo-cache layer).

## AI model (provider)
The backend and the Vercel handlers auto-pick the first available image model
from the environment, falling back to the offline mock (no keys needed):

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
- `backend/app.py` — Flask dev API wiring the frontend to `ai/`
  (sessions, polling, per-asset regenerate, zip export)
- `api/` — Vercel serverless handlers (same API, one-shot responses)
- `frontend/index.html` — demo UI (works with both backends)
- `demo/` — pre-generated real AI demo set (static, Vercel)
- Test the pipeline offline: `pytest ai/tests -q` and
  `python ai/scripts/run_test.py --provider mock`
