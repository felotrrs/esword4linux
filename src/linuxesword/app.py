"""Punto de entrada de la aplicación."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, __version__, i18n
from .config import Settings, asset
from .core.context import AppContext
from .ui.checkstyle import install as install_check_style
from .ui.main_window import MainWindow
from .ui.theme import stylesheet


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    settings = Settings.load()
    if not settings.first_run_done:
        settings.locale = i18n.detect()
    i18n.set_locale(settings.locale)

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("linuxEsword")
    app.setStyle("Fusion")
    app.setFont(QFont("Noto Sans", max(9, settings.font_size - 2)))
    # El proxy debe instalarse antes de la hoja de estilo para que dibuje el
    # indicador (caja + check) en lugar de que el QSS lo sustituya.
    install_check_style(app, settings.theme)
    app.setStyleSheet(stylesheet(settings.theme, settings.font_size))

    try:
        ctx = AppContext(settings)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(
            None, "linuxEsword",
            f"No se pudo abrir el catálogo:\n{exc}\n\n"
            f"Ruta de caché: {settings.cache_dir}",
        )
        return 1

    icon = asset("linuxesword.png")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))

    window = MainWindow(ctx)
    window.show()
    settings.first_run_done = True
    settings.save()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
