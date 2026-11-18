"""The About dialog must expose the GPL and Qt/PySide6 LGPL notices."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N = ROOT / "src" / "esword4linux" / "i18n"


def test_about_license_notice_in_both_locales():
    for locale in ("en", "es"):
        data = json.loads((I18N / f"{locale}.json").read_text(encoding="utf-8"))
        text = data["dialog.about.text"]
        assert "GPL-3.0" in text
        assert "Qt" in text
        assert "PySide6" in text
        assert "LGPL-3.0" in text
        assert "https://www.gnu.org/licenses/lgpl-3.0.html" in text
        assert "/usr/share/doc/esword4linux/LGPL-COMPLIANCE.md" in text
