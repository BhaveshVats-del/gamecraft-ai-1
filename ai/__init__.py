"""GameCraft AI: AI pipeline package (concept -> consistent game asset set)."""
try:  # optional: load keys from .env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from .pipeline import (Session, contact_sheet, generate_asset_set,  # noqa: E402,F401
                       naive_baseline, regenerate_asset)
from .prompts import ASSET_TYPES  # noqa: E402
from .providers import default_provider_name, get_provider  # noqa: E402,F401
from .styles import DEFAULT_STYLE, STYLES, list_styles  # noqa: E402,F401

__version__ = "1.1.0"

from .cache import find_cached, generate_or_cached, load_cached_set, pregenerate_demos  # noqa: E402,F401
