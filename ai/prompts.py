"""Step 1: concept -> structured plan (style descriptor, palette, 6 asset prompts)."""
import json
import os

from .styles import DEFAULT_STYLE, STYLES

ASSET_TYPES = ["character", "environment", "weapon", "icon_1", "icon_2", "icon_3"]

SYSTEM_PROMPT = """You are an art director for a game studio. Given a game concept and a fixed art style,
produce a cohesive asset plan so every asset looks like it belongs to the same game.

Return ONLY JSON with this shape:
{
  "world_notes": "one sentence on the setting/tone",
  "assets": [
    {"type": "character",   "name": "...", "prompt": "..."},
    {"type": "environment", "name": "...", "prompt": "..."},
    {"type": "weapon",      "name": "...", "prompt": "..."},
    {"type": "icon_1",      "name": "...", "prompt": "..."},
    {"type": "icon_2",      "name": "...", "prompt": "..."},
    {"type": "icon_3",      "name": "...", "prompt": "..."}
  ]
}
Rules:
- Exactly those 6 types, in that order.
- Each prompt describes ONLY the subject (shape, materials, key details, mood). Do NOT describe the art style,
  medium, or colors of the rendering; the style is added separately.
- Reuse the same motifs, materials and color story across all assets (e.g. same faction emblem, same metal).
- character: one full-body character, front view. environment: wide scene, no characters.
  weapon: one weapon, side view. icons: three distinct inventory items (potion, key, resource, etc.).
- Prompts are 15-40 words, concrete, no text/letters in the image."""

PLAN_SCHEMA = {
    "name": "asset_plan",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["world_notes", "assets"],
        "properties": {
            "world_notes": {"type": "string"},
            "assets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "name", "prompt"],
                    "properties": {
                        "type": {"type": "string", "enum": ASSET_TYPES},
                        "name": {"type": "string"},
                        "prompt": {"type": "string"},
                    },
                },
            },
        },
    },
}


def validate_plan(plan):
    assets = {a["type"]: a for a in plan["assets"]}
    missing = [t for t in ASSET_TYPES if t not in assets or not assets[t].get("prompt")]
    if missing:
        raise ValueError(f"plan missing assets: {missing}")
    plan["assets"] = [assets[t] for t in ASSET_TYPES]
    return plan


def fallback_plan(concept):
    """No-LLM plan so the demo never dies on a parse error or API outage."""
    c = concept.strip()
    return {
        "world_notes": c,
        "assets": [
            {"type": "character", "name": "Hero", "prompt": f"main hero of a game about: {c}; full body, front view, distinctive outfit and one signature accessory"},
            {"type": "environment", "name": "Main Location", "prompt": f"wide establishing scene of the main location in a game about: {c}; no characters, atmospheric depth"},
            {"type": "weapon", "name": "Signature Weapon", "prompt": f"the hero's signature weapon for a game about: {c}; single item, side view, detailed"},
            {"type": "icon_1", "name": "Consumable", "prompt": f"a consumable healing item from a game about: {c}; single object, centered"},
            {"type": "icon_2", "name": "Key Item", "prompt": f"a key quest item from a game about: {c}; single object, centered"},
            {"type": "icon_3", "name": "Resource", "prompt": f"a crafting resource from a game about: {c}; single object, centered"},
        ],
    }


def parse_plan_text(text):
    """Parse an LLM reply into a validated plan (tolerates ```json fences)."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    return validate_plan(json.loads(t.strip()))


def pick_plan_llm():
    """PLAN_LLM = openai | gemini | none | auto (default). auto: openai key, else gemini key, else none."""
    choice = os.getenv("PLAN_LLM", "auto").lower()
    if choice != "auto":
        return choice
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "none"


def _user_msg(concept, style_id):
    return f"Game concept: {concept}\nArt style (for context only): {STYLES[style_id]['label']}"


def _plan_openai(concept, style_id):
    from openai import OpenAI
    r = OpenAI().chat.completions.create(
        model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": _user_msg(concept, style_id)}],
        response_format={"type": "json_schema", "json_schema": PLAN_SCHEMA},
        temperature=0.8,
    )
    return parse_plan_text(r.choices[0].message.content)


def _plan_gemini(concept, style_id):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    r = client.models.generate_content(
        model=os.getenv("GEMINI_LLM_MODEL", "gemini-2.5-flash"),
        contents=_user_msg(concept, style_id),
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT,
                                           response_mime_type="application/json", temperature=0.8),
    )
    return parse_plan_text(r.text)


def expand_concept(concept, style_id, retries=2):
    """Validated plan dict. Never raises: falls back to the template plan."""
    if style_id not in STYLES:  # generate_asset_set already normalises; this covers direct callers
        style_id = DEFAULT_STYLE
    fn = {"openai": _plan_openai, "gemini": _plan_gemini}.get(pick_plan_llm())
    if fn:
        for _ in range(retries + 1):
            try:
                return fn(concept, style_id)
            except Exception:
                continue
    return fallback_plan(concept)


def build_final_prompt(asset, style_id, has_reference):
    s = STYLES[style_id]
    t = asset["type"]
    layout = {
        "character": "full-body character sheet pose, front view, plain neutral background",
        "environment": "wide landscape scene, no characters, no text",
        "weapon": "single weapon, side view, centered, plain neutral background",
    }.get(t, "single game inventory icon, centered, isolated on a plain solid background, no text")
    palette = ", ".join(s["palette"])
    core = f"{asset['prompt']}. {layout}. Style: {s['descriptor']}. Color palette: {palette}."
    if has_reference:
        return ("Use the attached image ONLY as the style reference: match its rendering technique, line quality, "
                "lighting and color palette exactly, but draw a completely different subject. Subject: " + core)
    return core
