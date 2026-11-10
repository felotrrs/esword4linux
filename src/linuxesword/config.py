"""Configuración y rutas de la aplicación.

Todo el estado escribible vive en `StorageC` (el home está al 81% de uso).
Ningún archivo de la carpeta de recursos se modifica jamás.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import APP_NAME


def _xdg(env: str, default: str) -> Path:
    return Path(os.environ.get(env) or default).expanduser()


# Directorio de datos de usuario (settings, logs). Pequeño, va al home.
CONFIG_DIR = _xdg("XDG_CONFIG_HOME", "~/.config") / APP_NAME.lower()
SETTINGS_FILE = CONFIG_DIR / "settings.json"

# Cache pesada (catálogo + índice FTS5). Debe vivir en StorageC.
DEFAULT_CACHE_DIR = Path("/home/felipe/StorageC/linuxEsword/.cache")
DEFAULT_RESOURCES_DIR = Path("/home/felipe/StorageA/Biblias/Biblias_bblx")

# Módulos que se indexan al primer arranque para que la app sea usable de
# inmediato: dos biblias base + el comentario RV1960 que las acompaña.
DEFAULT_PREINDEX = [
    "BIBLIAS/bible_lbla_es.bblx",
    "BIBLIAS/bible_rv1960_es_2.bblx",
    "COMENTARIOS/comment_rvr1960x_es.cmti",
]


@dataclass
class Settings:
    resources_dir: str = str(DEFAULT_RESOURCES_DIR)
    cache_dir: str = str(DEFAULT_CACHE_DIR)
    locale: str = "es"                 # es | en
    theme: str = "light"               # light | dark
    font_family: str = "Noto Serif"
    font_size: int = 15
    bible_module: str = "BIBLIAS/bible_rv1960_es_2.bblx"
    secondary_bible: str = ""
    commentary_modules: list[str] = field(default_factory=list)
    show_commentary_inline: bool = True
    show_strongs: bool = True
    preindex: list[str] = field(default_factory=lambda: list(DEFAULT_PREINDEX))
    last_reference: str = "Juan 3:16"
    window_geometry: str = ""
    open_tabs: list[dict] = field(default_factory=list)
    search_scope: list[int] = field(default_factory=list)  # module ids
    first_run_done: bool = False

    # ── persistencia ────────────────────────────────────────────────────
    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp = SETTINGS_FILE.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(SETTINGS_FILE)

    # ── rutas derivadas ─────────────────────────────────────────────────
    @property
    def cache_path(self) -> Path:
        p = Path(self.cache_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def catalog_db(self) -> Path:
        return self.cache_path / "catalog.db"

    @property
    def content_db(self) -> Path:
        return self.cache_path / "content.db"

    @property
    def resources_path(self) -> Path:
        return Path(self.resources_dir)
