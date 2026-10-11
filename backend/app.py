"""GameCraft AI backend.

Connects the REST API (and the frontend) to the ``ai/`` pipeline:

    concept + style  ->  ai.generate_asset_set  (mock | openai | gemini | replicate)

The provider ("ai model") is chosen from the environment:
``IMAGE_PROVIDER`` if set, else the first available key
(GEMINI_API_KEY / OPENAI_API_KEY / REPLICATE_API_TOKEN), else the offline
mock. See ``ai/.env.example``.

Run:
    pip install flask && pip install -r ai/requirements.txt
    python backend/app.py            # http://localhost:8000

API:
    GET  /api/health                          provider + liveness
    GET  /api/styles                          style presets (with palettes)
    POST /api/generate   {concept, style?, provider?, use_cache?}  -> {session_id}
    GET  /api/status/<session_id>             per-asset progress
    POST /api/regenerate/<session_id>/<type>  re-roll one asset
    GET  /api/assets/<session_id>/<file>      generated PNGs
    GET  /api/export/<session_id>             zip of the whole set
"""
import io
import os
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, request, send_file, send_from_directory  # noqa: E402

from ai import (  # noqa: E402
    ASSET_TYPES,
    DEFAULT_STYLE,
    STYLES,
    contact_sheet,
    generate_asset_set,
    list_styles,
    regenerate_asset,
)

FRONTEND_DIR = REPO_ROOT / "frontend"
OUT_ROOT = Path(os.environ.get("GAMECRAFT_OUT", str(REPO_ROOT / "outputs")))

app = Flask(__name__)
SESSIONS: dict[str, dict] = {}
_LOCK = threading.Lock()


# ------------------------------------------------------------------ provider


def default_provider() -> str:
    """Explicit IMAGE_PROVIDER wins; otherwise the first configured key; else mock."""
    forced = os.getenv("IMAGE_PROVIDER")
    if forced:
        return forced.lower()
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("REPLICATE_API_TOKEN"):
        return "replicate"
    return "mock"


def _known_provider(name: str) -> bool:
    try:
        from ai.providers import _PROVIDERS
        return name in _PROVIDERS
    except Exception:
        return name in {"mock", "openai", "gemini", "replicate"}


# ------------------------------------------------------------------- sessions


def _job(sid: str, state: str, session=None, error: str | None = None, source: str | None = None):
    with _LOCK:
        SESSIONS[sid] = {"state": state, "session": session, "error": error,
                         "source": source, "created": time.time()}


def _job_or_404(sid: str):
    job = SESSIONS.get(sid)
    if job is None:
        return None, (jsonify(error="unknown session"), 404)
    return job, None


def _assets_view(sid: str, session) -> list[dict]:
    out = []
    for t in ASSET_TYPES:
        a = session.assets[t]
        out.append({
            "type": t,
            "name": a["name"],
            "status": a["status"],
            "error": a["error"],
            "url": f"/api/assets/{sid}/{os.path.basename(a['path'])}"
                   if a.get("path") and a["status"] == "done" else None,
        })
    return out


def _run_generation(sid: str, concept: str, style: str, provider: str, use_cache: bool):
    out_dir = OUT_ROOT / sid
    try:
        if use_cache:
            from ai import generate_or_cached
            session, source = generate_or_cached(concept, style, provider_name=provider,
                                                 out_dir=str(out_dir))
        else:
            session = generate_asset_set(concept, style, provider, out_dir=str(out_dir))
            source = "live"
        # Best-effort side-by-side sheet (the demo's money shot).
        paths = [session.assets[t]["path"] for t in ASSET_TYPES
                 if session.assets[t].get("path")]
        if paths:
            try:
                contact_sheet(paths, str(out_dir / "contact_sheet.png"), concept)
            except Exception:  # noqa: BLE001 - sheet is a bonus, never fatal
                pass
        _job(sid, "done", session, source=source)
    except Exception as exc:  # noqa: BLE001 - report, don't crash the worker
        _job(sid, "error", error=f"{type(exc).__name__}: {exc}")


# ------------------------------------------------------------------- routes


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(ok=True, provider=default_provider(), styles=len(STYLES),
                   assets=len(ASSET_TYPES))


@app.get("/api/styles")
def styles():
    return jsonify(styles=list_styles(), default=DEFAULT_STYLE, provider=default_provider())


@app.post("/api/generate")
def generate():
    body = request.get_json(silent=True) or {}
    concept = (body.get("concept") or "").strip()
    if not concept:
        return jsonify(error="concept is required"), 400
    style = body.get("style") or DEFAULT_STYLE
    if style not in STYLES:
        style = DEFAULT_STYLE
    provider = (body.get("provider") or default_provider()).lower()
    if not _known_provider(provider):
        return jsonify(error=f"unknown provider {provider!r}"), 400
    use_cache = bool(body.get("use_cache", False))

    sid = uuid.uuid4().hex[:12]
    _job(sid, "running")
    threading.Thread(target=_run_generation,
                     args=(sid, concept, style, provider, use_cache),
                     daemon=True).start()
    return jsonify(session_id=sid, status="running", provider=provider, style=style), 202


@app.get("/api/status/<sid>")
def status(sid: str):
    job, err = _job_or_404(sid)
    if err:
        return err
    if job["session"] is None:
        return jsonify(session_id=sid,
                       status="error" if job["state"] == "error" else "running",
                       error=job.get("error"))
    s = job["session"]
    done = sum(1 for a in s.assets.values() if a["status"] == "done")
    return jsonify(session_id=sid, status=job["state"], source=job.get("source"),
                   concept=s.concept, style=s.style,
                   done=done, total=len(s.assets),
                   assets=_assets_view(sid, s))


@app.post("/api/regenerate/<sid>/<asset_type>")
def regenerate(sid: str, asset_type: str):
    if asset_type not in ASSET_TYPES:
        return jsonify(error=f"unknown asset type {asset_type!r}"), 400
    job, err = _job_or_404(sid)
    if err:
        return err
    s = job["session"]
    if s is None or job["state"] != "done":
        return jsonify(error="session is still running"), 409

    def run():
        try:
            regenerate_asset(s, asset_type)
        except Exception as exc:  # noqa: BLE001
            s.assets[asset_type].update(status="error", error=str(exc))

    threading.Thread(target=run, daemon=True).start()
    return jsonify(status="generating"), 202


@app.get("/api/assets/<sid>/<path:filename>")
def asset_file(sid: str, filename: str):
    job, err = _job_or_404(sid)
    if err:
        return err
    out_dir = (OUT_ROOT / sid).resolve()
    target = (out_dir / filename).resolve()
    if not str(target).startswith(str(out_dir)) or not target.is_file():
        return jsonify(error="not found"), 404
    return send_file(target)


@app.get("/api/export/<sid>")
def export(sid: str):
    job, err = _job_or_404(sid)
    if err:
        return err
    out_dir = OUT_ROOT / sid
    if not out_dir.is_dir():
        return jsonify(error="not found"), 404
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(out_dir.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(out_dir))
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"gamecraft_{sid}.zip", mimetype="application/zip")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    app.run(host="0.0.0.0", port=port, debug=False)
