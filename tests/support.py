"""Shared test helpers for optional real-module tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

_RAW = os.environ.get("ESWORD4LINUX_TEST_CORPUS", "").strip()
CORPUS = Path(_RAW).expanduser() if _RAW else Path("/nonexistent")


def corpus_available() -> bool:
    return CORPUS.is_dir()


requires_corpus = pytest.mark.skipif(
    not CORPUS.is_dir(),
    reason="set ESWORD4LINUX_TEST_CORPUS to a folder with e-Sword modules",
)
