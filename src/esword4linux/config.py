"""Application settings and paths.

All writable state lives under the XDG directories. No file inside the
user-selected modules folder is ever modified.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import APP_NAME


def _xdg(env: str, default: str) -> Path:
    return Path(os.environ.get(env) or default).expanduser()


def asset(name: str) -> Path:
    """Path to a bundled resource (icons)."""
    return Path(__file__).resolve().parent / "assets" / name


# Small user data (settings, logs) goes to the config directory.
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", "~/.config") / APP_NAME
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Heavy cache (catalog + FTS5 index). Regenerable at any time.
DEFAULT_CACHE_DIR = _xdg("XDG_CACHE_HOME", "~/.cache") / APP_NAME


@dataclass
class Settings:
    # Empty until the user picks a folder on first run.
    resources_dir: str = ""
    cache_dir: str = str(DEFAULT_CACHE_DIR)
    locale: str = "en"                  # en | es
    theme: str = "light"                # light | dark
    # Typography per role: interface, Scripture and running text (commentaries,
    # dictionaries, search). Edited in Edit -> Preferences.
    ui_font_family: str = "Noto Sans"
    ui_font_size: int = 13
    font_family: str = "Noto Serif"
    font_size: int = 15
    content_font_family: str = "Noto Sans"
    content_font_size: int = 13
    # User choices. Empty means "detect from the catalog at runtime".
    bible_module: str = ""
    secondary_bible: str = ""
    commentary_modules: list[str] = field(default_factory=list)
    show_commentary_inline: bool = True
    show_strongs: bool = True
    last_reference: str = ""
    window_geometry: str = ""
    open_tabs: list[dict] = field(default_factory=list)
    search_scope: list[int] = field(default_factory=list)  # module ids

    # ── panels and workspace tabs ───────────────────────────────────────
    sidebar_visible: bool = True
    sidebar_mode: str = "kind"          # compatibility; use sidebar_grouping
    sidebar_grouping: list[str] = field(default_factory=lambda: ["kind"])
    sidebar_kind_filters: list[str] = field(default_factory=list)
    sidebar_language_filters: list[str] = field(default_factory=list)
    show_unclassified: bool = False
    library_list_visible: bool = True   # dictionary term panel
    library_list_width: int = 300
    workspaces: list[dict] = field(default_factory=list)
    workspace_active: int = 0
    commentary_split: int = 280          # commentary panel height (px)
    parallel_split: int = 640            # main Bible width
    encrypted_ready: bool = False
    strong_rel: str = ""                 # selected Strong lexicon
    reference_bible: str = ""            # Bible used for verse pop-ups ("" = active)
    bottom_page: str = "commentary"      # commentary | strong | citations

    # ── persistence ─────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        # Ensure the config directory exists; if it is read-only (e.g. in CI or
        # offscreen tests), fall back to a writable temporary location.
        global SETTINGS_FILE
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            tmp = SETTINGS_FILE.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(SETTINGS_FILE)
        except OSError:
            # Safe for transient runs; does not affect user data.
            fallback_dir = Path("/tmp") / "esword4linux_config"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_file = fallback_dir / "settings.json"
            fallback_tmp = fallback_file.with_suffix(".json.tmp")
            fallback_tmp.write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            fallback_tmp.replace(fallback_file)
            SETTINGS_FILE = fallback_file

    # ── derived paths ───────────────────────────────────────────────────
    @property
    def cache_path(self) -> Path:
        p = Path(self.cache_dir).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def catalog_db(self) -> Path:
        return self.cache_path / "catalog.db"

    @property
    def content_db(self) -> Path:
        return self.cache_path / "content.db"

    @property
    def resources_path(self) -> Path | None:
        """Selected modules folder, or None when the user has not chosen one."""
        return Path(self.resources_dir).expanduser() if self.resources_dir else None

    @property
    def has_resources(self) -> bool:
        path = self.resources_path
        return path is not None and path.is_dir()
