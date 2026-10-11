"""Vercel serverless handler: GET /api/styles"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai import DEFAULT_STYLE, default_provider_name, list_styles  # noqa: E402


def handler(req, res):
    return res.status(200).json({"styles": list_styles(),
                                 "default": DEFAULT_STYLE,
                                 "provider": default_provider_name()})
