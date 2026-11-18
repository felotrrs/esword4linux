"""The installed icons must map to the canonical src assets."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src" / "esword4linux" / "assets" / "esword4linux.png"
ABOUT = ROOT / "src" / "esword4linux" / "assets" / "esword4linux-about.png"


def test_app_and_about_are_distinct_assets():
    assert APP.is_file() and ABOUT.is_file()
    assert APP.read_bytes() != ABOUT.read_bytes()


def test_packaging_apps_match_src_assets():
    apps = ROOT / "packaging" / "icons" / "apps"
    assert (apps / "esword4linux.png").read_bytes() == APP.read_bytes()
    assert (apps / "esword4linux-about.png").read_bytes() == ABOUT.read_bytes()


def test_512_hicolor_is_the_app_icon():
    hicolor = ROOT / "packaging" / "icons" / "hicolor" / "512x512" / "apps" / "esword4linux.png"
    assert hicolor.read_bytes() == APP.read_bytes()


def test_icon_validator_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "validate_icons.py")],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
