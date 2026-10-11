"""Vercel serverless handler: GET /api/health"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai import ASSET_TYPES, STYLES, default_provider_name  # noqa: E402


def handler(req, res):
    return res.status(200).json({"ok": True, "provider": default_provider_name(),
                                 "styles": len(STYLES), "assets": len(ASSET_TYPES)})
