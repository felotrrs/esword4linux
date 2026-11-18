#!/usr/bin/env python3
"""Audit the licensing evidence for the esword4linux private runtime.

This is deliberately independent of the application: it validates the exact
wheelhouse, the wheel RECORD hashes, the ELF inventory checked into
``docs/licensing/elf-inventory.tsv``, the required license texts, the Debian
compliance-document installation, and optionally a built ``.deb``.

It never modifies the wheelhouse, the package or the installed runtime.

Usage:
  packaging/audit_licensing.py
  packaging/audit_licensing.py --deb dist/deb/esword4linux_0.5.0-1_amd64.deb
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WHEELHOUSE = REPO_ROOT / ".build" / "wheelhouse"
DEFAULT_REQUIREMENTS = REPO_ROOT / "packaging" / "runtime-requirements.txt"
INVENTORY = REPO_ROOT / "docs" / "licensing" / "elf-inventory.tsv"
SOURCE_MANIFEST = REPO_ROOT / "docs" / "licensing" / "source-release-manifest.md"
SOURCE_HASHES = REPO_ROOT / "docs" / "licensing" / "source-archives.sha256"
LICENSES = REPO_ROOT / "packaging" / "licenses"
DOC = REPO_ROOT / "docs" / "licensing" / "LGPL-COMPLIANCE.md"
SOURCES = REPO_ROOT / "docs" / "licensing" / "third-party-sources.md"
COPYRIGHT = REPO_ROOT / "debian" / "copyright"
INSTALL = REPO_ROOT / "debian" / "install"

sys.path.insert(0, str(REPO_ROOT / "packaging"))
import stage_runtime  # noqa: E402

EXPECTED_METADATA = {
    "pyside6-essentials": ("PySide6_Essentials", "6.12.0",
                           "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
    "shiboken6": ("shiboken6", "6.12.0",
                  "LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only"),
    "pyyaml": ("PyYAML", "6.0.3", "MIT"),
}

REQUIRED_LICENSES = (
    "LGPL-3.0-only.txt",
    "GPL-3.0-only.txt",
    "MIT.txt",
    "Unicode-3.0.txt",
    "QT-THIRD-PARTY.md",
    "Qt/MPL-2.0.txt",
    "Qt/LGPL-2.1-or-later.txt",
    "Qt/LicenseRef-BSD-3-Clause-with-PCRE2-Binary-Like-Packages-Exception.txt",
)


class AuditError(Exception):
    pass


def fail(message: str) -> "NoReturn":
    print(f"audit_licensing: FAIL: {message}", file=sys.stderr)
    raise AuditError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metadata(wheel: Path) -> tuple[str, str, str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata = next(n for n in archive.namelist()
                        if n.endswith(".dist-info/METADATA"))
        text = archive.read(metadata).decode("utf-8", errors="replace")
    fields = {}
    for line in text.splitlines():
        if not line.strip():
            break
        if ":" in line:
            key, value = line.split(":", 1)
            fields.setdefault(key, value.strip())
    return fields.get("Name", ""), fields.get("Version", ""), fields.get("License", "")


def verify_record(wheel: Path) -> int:
    with zipfile.ZipFile(wheel) as archive:
        record = next(n for n in archive.namelist()
                      if n.endswith(".dist-info/RECORD"))
        rows = list(csv.reader(archive.read(record).decode().splitlines()))
        checked = 0
        for row in rows:
            if len(row) < 2 or not row[1]:
                continue
            algorithm, expected = row[1].split("=", 1)
            data = archive.read(row[0])
            digest = base64.urlsafe_b64encode(
                hashlib.new(algorithm, data).digest()
            ).rstrip(b"=").decode()
            if digest != expected.rstrip("="):
                fail(f"RECORD hash mismatch in {wheel.name}: {row[0]}")
            checked += 1
    return checked


def readelf(path: Path, *args: str) -> str:
    env = {**os.environ, "LC_ALL": "C", "LANG": "C"}
    result = subprocess.run(["readelf", *args, str(path)], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=env)
    return result.stdout


def elf_rows(root: Path) -> list[dict[str, str]]:
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.read_bytes()[:4] != b"\x7fELF":
            continue
        header = readelf(path, "-h")
        dynamic = readelf(path, "-d")
        cls = re.search(r"Class:\s+(\S+)", header)
        machine = re.search(r"Machine:\s+(.+)", header)
        typ = re.search(r"Type:\s+(.+)", header)
        soname = re.findall(r"\(SONAME\)\s+Library soname: \[([^\]]+)\]", dynamic)
        needed = re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", dynamic)
        rpath = re.findall(r"\(RPATH\)\s+Library rpath: \[([^\]]+)\]", dynamic)
        runpath = re.findall(r"\(RUNPATH\)\s+Library runpath: \[([^\]]+)\]", dynamic)
        wheel = path.relative_to(root).parts[0]
        rows.append({
            "wheel": wheel,
            "path": str(path.relative_to(root / wheel)),
            "size": str(path.stat().st_size),
            "sha256": sha256(path),
            "cls": cls.group(1) if cls else "",
            "machine": machine.group(1).strip() if machine else "",
            "typ": typ.group(1).strip() if typ else "",
            "soname": ";".join(soname),
            "needed": ";".join(needed),
            "rpath": ";".join(rpath),
            "runpath": ";".join(runpath),
        })
    return rows


def wheel_elf_rows(wheelhouse: Path) -> list[dict[str, str]]:
    """Extract only ELF entries to a temporary tree, then inventory them."""
    with tempfile.TemporaryDirectory(prefix="esw-license-audit-") as tmp:
        root = Path(tmp)
        for wheel in sorted(wheelhouse.glob("*.whl")):
            target = root / wheel.stem
            with zipfile.ZipFile(wheel) as archive:
                for name in archive.namelist():
                    if name.endswith("/"):
                        continue
                    with archive.open(name) as handle:
                        if handle.read(4) != b"\x7fELF":
                            continue
                    destination = target / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(archive.read(name))
        return elf_rows(root)


def check_inventory(wheelhouse: Path) -> None:
    if not INVENTORY.is_file():
        fail(f"missing {INVENTORY}")
    with INVENTORY.open(encoding="utf-8") as handle:
        checked = list(csv.DictReader(handle, delimiter="\t"))
    actual = wheel_elf_rows(wheelhouse)
    if len(checked) != len(actual):
        fail(f"ELF inventory count {len(checked)} != actual {len(actual)}")
    by_path = {(row["wheel"], row["path"]): row for row in actual}
    for row in checked:
        key = (row["wheel"], row["path"])
        if key not in by_path:
            fail(f"inventory path not found: {key}")
        other = by_path[key]
        for field in ("size", "sha256", "cls", "machine", "typ",
                      "soname", "needed", "rpath", "runpath"):
            if row[field] != other[field]:
                fail(f"inventory mismatch for {key} field {field}")
    print(f"PASS ELF inventory ({len(checked)} objects match docs/licensing/elf-inventory.tsv)")


def check_wheels(wheelhouse: Path, requirements: Path) -> None:
    try:
        wheels = stage_runtime.verify_wheelhouse(wheelhouse, requirements)
    except SystemExit as exc:
        fail(f"wheelhouse validation failed (exit {exc.code})")
    if set(wheels) != set(EXPECTED_METADATA):
        fail(f"unexpected wheel set: {sorted(wheels)}")
    for key, path in sorted(wheels.items()):
        name, version, license_text = read_metadata(path)
        expected = EXPECTED_METADATA[key]
        if (name, version, license_text) != expected:
            fail(f"unexpected metadata for {path.name}: "
                 f"{(name, version, license_text)!r}")
        count = verify_record(path)
        print(f"PASS wheel {key}: {path.name} ({count} RECORD hashes)")


def check_static_evidence() -> None:
    for path in (DOC, SOURCES, INVENTORY, SOURCE_MANIFEST, SOURCE_HASHES,
                 LICENSES, COPYRIGHT, INSTALL):
        if not path.exists():
            fail(f"missing required evidence: {path.relative_to(REPO_ROOT)}")
    for name in REQUIRED_LICENSES:
        if not (LICENSES / name).is_file():
            fail(f"missing license text: packaging/licenses/{name}")

    source_hashes = SOURCE_HASHES.read_text(encoding="utf-8")
    for line in (
        "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751  pyside-setup-everywhere-src-6.12.0.tar.xz",
        "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165  qt-everywhere-src-6.12.0.tar.xz",
    ):
        if line not in source_hashes:
            fail(f"source checksum manifest is missing: {line}")
    manifest = SOURCE_MANIFEST.read_text(encoding="utf-8")
    for needle in ("`PUBLISHED`", "v0.5.0-lgpl-sources",
                   "443,394,020", "18,211,772",
                   "releases/download/v0.5.0-lgpl-sources/qt-everywhere-src-6.12.0.tar.xz",
                   "releases/download/v0.5.0-lgpl-sources/pyside-setup-everywhere-src-6.12.0.tar.xz"):
        if needle not in manifest:
            fail(f"source release manifest is missing {needle}")

    install = INSTALL.read_text(encoding="utf-8")
    if "docs/licensing/LGPL-COMPLIANCE.md" not in install:
        fail("LGPL-COMPLIANCE.md is not installed by debian/install")

    copyright_text = COPYRIGHT.read_text(encoding="utf-8")
    files_lines = [line for line in copyright_text.splitlines()
                   if line.startswith("Files:")]
    if not files_lines or files_lines[0] != "Files: *":
        fail("the general Files: * stanza is not first in debian/copyright")
    for needle in ("Files: .build/wheelhouse/*", "LGPL-3.0-only",
                   "Unicode-3.0", "shiboken6", "License: MPL-2.0",
                   "License: LGPL-2.1-or-later"):
        if needle not in copyright_text:
            fail(f"debian/copyright is missing {needle}")

    archives = {
        "pyside-setup-everywhere-src-6.12.0.tar.xz":
            "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751",
        "qt-everywhere-src-6.12.0.tar.xz":
            "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165",
    }
    for name, expected in archives.items():
        local = REPO_ROOT / "dist" / "source-archives" / name
        if local.is_file():
            if sha256(local) != expected:
                fail(f"local source archive hash mismatch: {name}")
        else:
            print(f"NOTE local source archive not staged: {name}")

    doc = DOC.read_text(encoding="utf-8")
    for needle in ("qt-everywhere-src-6.12.0.tar.xz",
                   "pyside-setup-everywhere-src-6.12.0.tar.xz",
                   "98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165",
                   "099c1a597cf33c1b000e11cf68a0b82d216fb802bf81726efc720394f10c7751",
                   "Installation Information"):
        if needle not in doc:
            fail(f"LGPL-COMPLIANCE.md is missing {needle}")
    print("PASS static licensing evidence")


def check_deb(path: Path) -> None:
    if not path.is_file():
        fail(f"missing .deb: {path}")
    result = subprocess.run(["dpkg-deb", "--contents", str(path)],
                            text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if result.returncode != 0:
        fail(f"dpkg-deb failed: {result.stderr.strip()}")
    contents = result.stdout
    paths = set()
    for line in contents.splitlines():
        match = re.search(r"\s(\./\S+)$", line)
        if match:
            paths.add(match.group(1))
    for required in (
        "./usr/bin/esword4linux",
        "./usr/share/doc/esword4linux/LGPL-COMPLIANCE.md",
        "./usr/share/doc/esword4linux/licenses/LGPL-3.0-only.txt.gz",
        "./opt/esword4linux/RUNTIME-MANIFEST.yaml",
        "./opt/esword4linux/python/PySide6/QtCore.abi3.so",
        "./opt/esword4linux/python/shiboken6/libshiboken6.abi3.so.6.12",
        "./opt/esword4linux/python/yaml/__init__.py",
    ):
        if required not in paths:
            fail(f"installed package is missing {required}")
    for forbidden in (".whl", "wheelhouse", "site-packages", "__pycache__", ".pyc"):
        if forbidden in contents:
            fail(f"installed package contains forbidden {forbidden}")
    print(f"PASS installed package contents: {path.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheelhouse", type=Path, default=DEFAULT_WHEELHOUSE)
    parser.add_argument("--requirements", type=Path,
                        default=DEFAULT_REQUIREMENTS)
    parser.add_argument("--deb", type=Path,
                        help="also inspect a built .deb")
    args = parser.parse_args(argv)

    if not args.wheelhouse.is_dir():
        fail(f"wheelhouse not found: {args.wheelhouse}")
    check_wheels(args.wheelhouse, args.requirements)
    check_static_evidence()
    check_inventory(args.wheelhouse)
    if args.deb:
        check_deb(args.deb)
    print("AUDIT PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError:
        raise SystemExit(1)
