#!/usr/bin/env python3
"""Detect duplicate e-Sword modules and keep one copy of each.

Two copies are duplicates if they have **the same bytes** (sha256). Files of
the same size are grouped first so large libraries are not hashed needlessly.

Usage:
    python tools/deduplicate.py                     # report to the console
    python tools/deduplicate.py --write-report      # + reports/duplicates.md
    python tools/deduplicate.py --apply             # move extras to _duplicados/
    python tools/deduplicate.py --apply --mode delete
    python tools/deduplicate.py --apply --dry-run

The quarantine is **reversible**: files are moved (not deleted) and a manifest
is written with the original path, sha256 and the kept copy.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from esword4linux.config import Settings  # noqa: E402
from esword4linux.core.catalog import Catalog, work_key  # noqa: E402

MODULE_EXTS = {
    ".bblx", ".bbli", ".cmtx", ".cmti", ".dctx", ".dcti", ".devx", ".topx",
    ".topi", ".refx", ".refi", ".harx", ".mapx", ".twm", ".lexi", ".lexx",
    ".lanx", ".en", ".es", ".fr", ".pt",
}

# Canonical folder per content kind.
KIND_FOLDER = {
    "bible": "BIBLIAS",
    "commentary": "COMENTARIOS",
    "dictionary": "DICCIONARIOS",
    "lexicon": "DICCIONARIOS",
    "devotion": "DEVOCIONALES",
    "topic": "TOPICOS",
    "reference": "LIBROS",
    "harmony": "ARMONIAS",
    "maps": "MAPAS",
}

NORMALIZED_PREFIX = (
    "bible_", "comment_", "dicc_", "topic_", "devotion_", "harmony_",
    "map_", "lexicon_", "twm_", "dev_",
)

ROLE_ES = {
    "bible": "Text", "commentary": "Notes", "dictionary": "Dictionary",
    "lexicon": "Lexicon", "devotion": "Devotional", "topic": "Topics",
    "reference": "Reference", "harmony": "Harmony", "maps": "Maps",
    "twm": "TWM", "unknown": "Other",
}


@dataclass
class Entry:
    path: Path
    rel: str
    size: int
    sha: str
    kind: str
    title: str
    entries: int


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def keep_score(entry: Entry) -> float:
    """Higher score means more worth keeping."""
    score = 0.0
    parts = Path(entry.rel).parts
    folder = parts[0].upper() if len(parts) > 1 else ""
    want = KIND_FOLDER.get(entry.kind, "")
    if folder and want and folder == want:
        score += 30
    name = Path(entry.rel).name.lower()
    if name.startswith(NORMALIZED_PREFIX):
        score += 20
    ratio = difflib.SequenceMatcher(None, _norm(Path(name).stem), _norm(entry.title)).ratio()
    score += ratio * 12
    score += min(len(name), 120) * 0.2
    return score


def collect(root: Path) -> list[Entry]:
    files: list[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            path = Path(dirpath) / fn
            if path.suffix.lower() not in MODULE_EXTS:
                continue
            try:
                if path.stat().st_size == 0:
                    continue
            except OSError:
                continue
            files.append(path)
    return files_paths(files, root)


def files_paths(paths: list[Path], root: Path) -> list[Entry]:
    return [Entry(p, str(p.relative_to(root)), p.stat().st_size, "", "", "", 0) for p in paths]


def enrich(entries: list[Entry], catalog: Catalog) -> None:
    for e in entries:
        row = catalog.by_rel_path(e.rel)
        if row:
            e.kind = row["kind"]
            e.title = row["title"]
            e.entries = row["entries"]


def duplicate_groups(entries: list[Entry], progress=None) -> list[list[Entry]]:
    by_size: dict[int, list[Entry]] = collections.defaultdict(list)
    for e in entries:
        by_size[e.size].append(e)
    candidates = [group for group in by_size.values() if len(group) > 1]
    total = sum(len(g) for g in candidates)
    done = 0
    groups: list[list[Entry]] = []
    for group in candidates:
        by_hash: dict[str, list[Entry]] = collections.defaultdict(list)
        for e in group:
            e.sha = sha256(e.path)
            by_hash[e.sha].append(e)
            done += 1
            if progress and done % 25 == 0:
                progress(done, total)
        for sha, items in by_hash.items():
            if len(items) > 1:
                groups.append(items)
    groups.sort(key=lambda g: (-g[0].size, g[0].rel))
    return groups


def order_group(group: list[Entry]) -> list[Entry]:
    """Sort: keeper first, then the redundant copies."""
    return sorted(group, key=lambda e: (-keep_score(e), e.rel))


# ── report ───────────────────────────────────────────────────────────────
def build_report(root: Path, groups: list[list[Entry]], empty: list[str],
                 works: list[dict]) -> str:
    redundant = sum(len(g) - 1 for g in groups)
    wasted = sum(g[0].size * (len(g) - 1) for g in groups)
    lines = [
        "# Duplicates in the e-Sword library",
        "",
        f"- **Resources folder**: `{root}`",
        f"- **Generated**: {time.strftime('%Y-%m-%d %H:%M')}",
        f"- **Exact duplicate groups**: {len(groups)}",
        f"- **Redundant copies**: {redundant}",
        f"- **Redundant space**: {wasted / 1e6:.1f} MB",
        "",
        "Two files are duplicates if they have **the same bytes** (`sha256`).",
        "The ✅ marks the copy that is kept; 🗑 marks what would be quarantined.",
        "",
        "## Duplicate groups",
        "",
    ]
    for i, group in enumerate(groups, 1):
        ordered = order_group(group)
        keeper = ordered[0]
        lines.append(f"### {i}. {keeper.title or keeper.rel} — {keeper.size / 1e6:.1f} MB")
        lines.append("")
        lines.append("| | Role | File | Kind |")
        lines.append("|---|---|---|---|")
        for j, e in enumerate(ordered):
            mark = "✅ keep" if j == 0 else "🗑 quarantine"
            role = ROLE_ES.get(e.kind, e.kind or "?")
            lines.append(f"| {mark} | {role} | `{e.rel}` | `{e.kind or '?'}` |")
        lines.append("")
        lines.append(f"<sub>sha256 `{keeper.sha[:16]}…`</sub>")
        lines.append("")

    if works:
        lines += [
            "## Same work, different files",
            "",
            "These are not byte-for-byte duplicates (left untouched): the same",
            "work split across several modules. The sidebar groups them in the",
            "**By work** view.",
            "",
            "| Work | Modules |",
            "|---|---|",
        ]
        for work in works:
            mods = " · ".join(
                f"{ROLE_ES.get(m['kind'], m['kind'])} (`{Path(m['rel_path']).name}`)"
                for m in work["modules"]
            )
            lines.append(f"| {work['title']} | {mods} |")
        lines.append("")

    if empty:
        lines += [
            "## Empty files (0 bytes)",
            "",
            "Not valid modules; they can simply be deleted.",
            "",
        ]
        lines += [f"- `{rel}`" for rel in empty]
        lines.append("")
    return "\n".join(lines)


# ── actions ──────────────────────────────────────────────────────────────
def apply_groups(root: Path, groups: list[list[Entry]], mode: str,
                 dry_run: bool) -> int:
    if mode == "move":
        dest_root = root / "_duplicados" / time.strftime("%Y%m%d-%H%M%S")
    else:
        dest_root = None
    manifest = []
    moved = 0
    for group in groups:
        ordered = order_group(group)
        keeper = ordered[0]
        for entry in ordered[1:]:
            record = {
                "from": entry.rel,
                "sha256": entry.sha,
                "size": entry.size,
                "keeper": keeper.rel,
                "mode": mode,
            }
            if dry_run:
                print(f"  [dry-run] {mode}: {entry.rel}  (keeping {keeper.rel})")
                moved += 1
                continue
            if mode == "move":
                target = dest_root / entry.rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(entry.path), str(target))
                record["to"] = str(target.relative_to(root))
            else:
                entry.path.unlink()
            manifest.append(record)
            moved += 1

    if not dry_run:
        base = root / "_duplicados"
        base.mkdir(exist_ok=True)
        manifest_path = base / f"manifest-{time.strftime('%Y%m%d-%H%M%S')}.json"
        manifest_path.write_text(
            json.dumps({"root": str(root), "mode": mode, "moved": manifest},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nManifest: {manifest_path}")
    return moved


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resources", default=None)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mode", choices=["move", "delete"], default="move")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write-report", action="store_true")
    ap.add_argument("--report", default=None,
                    help="report path (default: reports/duplicates.md)")
    args = ap.parse_args()

    settings = Settings.load()
    raw_root = args.resources or settings.resources_dir
    if not raw_root:
        print("No modules folder selected. Use --resources DIR or choose one "
              "in the application.")
        return 2
    root = Path(raw_root).expanduser()
    if not root.is_dir():
        print(f"Folder not found: {root}")
        return 1

    catalog = Catalog(settings.catalog_db)
    print(f"Analyzing {root} …")
    entries = collect(root)
    enrich(entries, catalog)
    print(f"  modules with content: {len(entries)}")

    def progress(done: int, total: int) -> None:
        sys.stderr.write(f"\r  hash {done}/{total}")
        sys.stderr.flush()

    groups = duplicate_groups(entries, progress)
    sys.stderr.write("\n")

    empty = [
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in MODULE_EXTS and p.stat().st_size == 0
    ]
    works = [w for w in catalog.works() if len(w["modules"]) > 1]

    redundant = sum(len(g) - 1 for g in groups)
    wasted = sum(g[0].size * (len(g) - 1) for g in groups)
    print(f"\nDuplicate groups: {len(groups)} · redundant copies: {redundant} · "
          f"{wasted / 1e6:.1f} MB")
    print(f"Empty files: {len(empty)} · works with several modules: {len(works)}")

    if args.write_report or not args.apply:
        report = build_report(root, groups, empty, works)
        if args.write_report:
            out = (Path(args.report).expanduser() if args.report
                   else ROOT / "reports" / "duplicates.md")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(report, encoding="utf-8")
            print(f"Report: {out}")
        else:
            print("\n" + report)

    if not args.apply:
        print("\n(use --apply to move redundant copies to _duplicados/)")
        return 0

    moved = apply_groups(root, groups, args.mode, args.dry_run)
    print(f"\n{'Simulated' if args.dry_run else 'Processed'}: {moved} copies")
    if not args.dry_run:
        print("Rescan the library to update the catalog:  make scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
