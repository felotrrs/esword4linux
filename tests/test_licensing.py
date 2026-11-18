"""Static and optional runtime checks for the licensing evidence."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WHEELHOUSE = ROOT / ".build" / "wheelhouse"


def test_compliance_document_is_installed():
    install = (ROOT / "debian" / "install").read_text(encoding="utf-8")
    assert "docs/licensing/LGPL-COMPLIANCE.md usr/share/doc/esword4linux" in install
    assert "docs/licensing/qt-runtime-inventory.md usr/share/doc/esword4linux" in install
    assert "docs/licensing/third-party-sources.md usr/share/doc/esword4linux" in install


def test_copyright_covers_wheelhouse_and_sources():
    text = (ROOT / "debian" / "copyright").read_text(encoding="utf-8")
    files_lines = [line for line in text.splitlines() if line.startswith("Files:")]
    assert files_lines[0] == "Files: *"
    assert "Files: .build/wheelhouse/*" in text
    assert "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751" in text
    assert "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165" in text
    assert "License: MPL-2.0" in text
    assert "License: LGPL-2.1-or-later" in text


def test_source_release_manifest_is_prepared_not_published():
    manifest = (ROOT / "docs" / "licensing" / "source-release-manifest.md").read_text(
        encoding="utf-8"
    )
    assert "READY-PENDING-PUBLICATION" in manifest
    assert "v0.5.0-lgpl-sources" in manifest
    assert "443,394,020" in manifest
    assert "18,211,772" in manifest
    hashes = (ROOT / "docs" / "licensing" / "source-archives.sha256").read_text(
        encoding="utf-8"
    )
    assert "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165" in hashes
    assert "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751" in hashes


def test_required_license_texts_exist():
    licenses = ROOT / "packaging" / "licenses"
    for name in (
        "LGPL-3.0-only.txt",
        "GPL-3.0-only.txt",
        "MIT.txt",
        "Unicode-3.0.txt",
        "QT-THIRD-PARTY.md",
        "Qt/MPL-2.0.txt",
        "Qt/LGPL-2.1-or-later.txt",
    ):
        assert (licenses / name).is_file(), name


def test_elf_inventory_is_complete():
    rows = (ROOT / "docs" / "licensing" / "elf-inventory.tsv").read_text(
        encoding="utf-8"
    ).splitlines()
    assert rows[0].startswith("wheel\tpath\tsize\tsha256")
    assert len(rows) == 289  # header + 288 ELF objects


@pytest.mark.skipif(not WHEELHOUSE.is_dir(),
                    reason="requires the Git-ignored wheelhouse")
def test_audit_licensing_script_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "packaging" / "audit_licensing.py")],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
