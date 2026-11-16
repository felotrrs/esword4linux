"""Minimal JSON-based i18n (no build step).

Usage:
    from ..i18n import tr, set_locale
    set_locale("en")
    tr("search.results_n", n=12, ms=34)
"""

from __future__ import annotations

import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent
_LOCALES = ("es", "en")
_catalog: dict[str, dict[str, str]] = {}
_current = "en"


def _load() -> None:
    if _catalog:
        return
    for lang in _LOCALES:
        path = _DIR / f"{lang}.json"
        try:
            _catalog[lang] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _catalog[lang] = {}


def available() -> tuple[str, ...]:
    return _LOCALES


def current() -> str:
    return _current


def set_locale(lang: str) -> None:
    global _current
    _load()
    _current = lang if lang in _LOCALES else "en"


def tr(key: str, **kwargs) -> str:
    _load()
    text = _catalog.get(_current, {}).get(key)
    if text is None:
        text = _catalog.get("en", {}).get(key)
    if text is None:
        text = _catalog.get("es", {}).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def detect() -> str:
    """System locale, falling back to English."""
    import os

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val.lower().startswith("en"):
            return "en"
        if val.lower().startswith("es"):
            return "es"
    return "en"
