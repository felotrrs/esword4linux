"""First-run behavior: no bundled modules and folder validation."""

from __future__ import annotations

from esword4linux.config import Settings
from esword4linux.ui.first_run import count_modules


def test_defaults_have_no_modules_or_preindex(tmp_path):
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    assert settings.resources_dir == ""
    assert settings.bible_module == ""
    assert settings.last_reference == ""
    assert not settings.has_resources
    assert not hasattr(settings, "preindex")
    assert settings.cache_path.name == "cache"


def test_count_modules_only_counts_esword_extensions(tmp_path):
    (tmp_path / "bible.bblx").write_bytes(b"")
    (tmp_path / "comment.cmtx").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("not a module", encoding="utf-8")
    nested = tmp_path / "BIBLES"
    nested.mkdir()
    (nested / "another.bbli").write_bytes(b"")
    assert count_modules(tmp_path) == 3
