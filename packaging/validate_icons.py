#!/usr/bin/env python3
"""Validate that packaged icons come from the canonical application assets.

This runs during the Debian build so a generated .deb cannot silently use a
different launcher icon or swap the application and About artwork.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "esword4linux" / "assets" / "esword4linux.png"
ABOUT = ROOT / "src" / "esword4linux" / "assets" / "esword4linux-about.png"
APPS = ROOT / "packaging" / "icons" / "apps"
HICOLOR = ROOT / "packaging" / "icons" / "hicolor"
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def fail(message: str) -> "NoReturn":
    print(f"validate_icons: error: {message}", file=sys.stderr)
    raise SystemExit(1)


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        fail(f"not a PNG image: {path}")
    return struct.unpack(">II", data[16:24])


def main() -> int:
    if not APP.is_file() or not ABOUT.is_file():
        fail("canonical src/esword4linux/assets icons are missing")
    if not APPS.is_dir() or not HICOLOR.is_dir():
        fail("packaging/icons is incomplete")

    app_bytes = APP.read_bytes()
    about_bytes = ABOUT.read_bytes()

    for name, expected in (
        ("esword4linux.png", app_bytes),
        ("esword4linux-about.png", about_bytes),
    ):
        path = APPS / name
        if not path.is_file() or path.read_bytes() != expected:
            fail(f"packaging/icons/apps/{name} is not the src asset")

    for size in SIZES:
        path = HICOLOR / f"{size}x{size}" / "apps" / "esword4linux.png"
        if not path.is_file():
            fail(f"missing hicolor icon: {path.relative_to(ROOT)}")
        if png_size(path) != (size, size):
            fail(f"wrong dimensions for {path.relative_to(ROOT)}")

    if (HICOLOR / "512x512" / "apps" / "esword4linux.png").read_bytes() != app_bytes:
        fail("512x512 hicolor icon is not byte-identical to the app asset")

    main_window = (ROOT / "src" / "esword4linux" / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    about_dialog = (ROOT / "src" / "esword4linux" / "ui" / "about_dialog.py").read_text(
        encoding="utf-8"
    )
    if 'asset("esword4linux.png")' not in main_window:
        fail("main_window.py does not use esword4linux.png")
    if 'asset("esword4linux-about.png")' not in about_dialog:
        fail("about_dialog.py does not use esword4linux-about.png")

    print("validate_icons: PASS (app and About assets map to the installed icons)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, struct.error) as exc:
        fail(str(exc))
