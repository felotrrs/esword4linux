"""Pytest fixtures for isolated settings and optional corpus tests."""

from __future__ import annotations

import sqlite3

import pytest

from esword4linux.config import Settings
from esword4linux.core.catalog import Catalog

try:
    from support import CORPUS, corpus_available
except ImportError:  # pragma: no cover - package-style collection
    from tests.support import CORPUS, corpus_available


@pytest.fixture
def empty_settings(tmp_path):
    """Settings pointing at a temporary, empty catalog."""
    return Settings(resources_dir="", cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def populated_settings(tmp_path):
    """Settings with synthetic catalog rows for widget tests."""
    settings = Settings(resources_dir="", cache_dir=str(tmp_path / "cache"))
    catalog = Catalog(settings.catalog_db)
    catalog.close()
    rows = [
        ("bible/test.bblx", "bible/test.bblx", "test.bblx", "bblx",
         "bible", "bible", "Test Bible", "TB", "es", 0, 10, 100, 1.0, "pending"),
        ("comment/test.cmti", "comment/test.cmti", "test.cmti", "cmti",
         "commentary", "commentary", "Test Commentary", "TC", "es", 0, 10, 100, 1.0, "pending"),
        ("dict/test.dctx", "dict/test.dctx", "test.dctx", "dctx",
         "dictionary", "dictionary", "Test Dictionary", "TD", "en", 0, 10, 100, 1.0, "pending"),
    ]
    conn = sqlite3.connect(settings.catalog_db)
    try:
        conn.executemany(
            "INSERT INTO module(path, rel_path, filename, ext, structure, kind, "
            "title, abbreviation, language, encrypted, entries, size, mtime, "
            "index_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return settings


@pytest.fixture
def corpus_context(tmp_path):
    """Real AppContext scanned from ESWORD4LINUX_TEST_CORPUS."""
    if not corpus_available():
        pytest.skip("set ESWORD4LINUX_TEST_CORPUS to a folder with e-Sword modules")
    from esword4linux.core.context import AppContext

    settings = Settings(resources_dir=str(CORPUS), cache_dir=str(tmp_path / "cache"))
    ctx = AppContext(settings)
    ctx.catalog.scan(CORPUS)
    yield ctx
    ctx.close_all()


@pytest.fixture
def corpus_catalog(tmp_path):
    """Catalog scanned from ESWORD4LINUX_TEST_CORPUS."""
    if not corpus_available():
        pytest.skip("set ESWORD4LINUX_TEST_CORPUS to a folder with e-Sword modules")
    catalog = Catalog(tmp_path / "catalog.db")
    catalog.scan(CORPUS)
    yield catalog
    catalog.close()
