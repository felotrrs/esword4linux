"""UI language labels and order."""

from __future__ import annotations

from ..core.catalog import LANGUAGE_ORDER
from ..i18n import tr

_INDEX = {code: i for i, code in enumerate(LANGUAGE_ORDER)}


def language_label(code: str) -> str:
    code = code or "und"
    label = tr(f"lang.{code}")
    if label == f"lang.{code}":
        return code.upper()
    return label


def language_sort_key(code: str) -> int:
    return _INDEX.get(code or "und", len(_INDEX))
