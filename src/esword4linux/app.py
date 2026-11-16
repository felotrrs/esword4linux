"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from . import APP_NAME, __version__, i18n
from .config import SETTINGS_FILE, Settings, asset
from .core.context import AppContext
from .ui.checkstyle import install as install_check_style
from .ui.first_run import FirstRunDialog
from .ui.main_window import MainWindow
from .ui.theme import ui_stylesheet


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)

    settings = Settings.load()
    if not SETTINGS_FILE.exists():
        settings.locale = i18n.detect()
    i18n.set_locale(settings.locale)

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName(APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont(settings.ui_font_family, settings.ui_font_size))
    # The proxy must be installed before the stylesheet so it draws the check
    # indicator (box + mark) instead of the QSS replacing it.
    install_check_style(app, settings.theme)
    app.setStyleSheet(ui_stylesheet(settings))

    icon = asset("esword4linux.png")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))

    # No bundled modules: ask for the user's folder before showing the window.
    if not settings.has_resources:
        dialog = FirstRunDialog(initial=settings.resources_dir)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return 0
        settings.resources_dir = dialog.selected_path()
        settings.save()

    try:
        ctx = AppContext(settings)
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(
            None,
            APP_NAME,
            f"Could not open the catalog:\n{exc}\n\n"
            f"Cache path: {settings.cache_dir}",
        )
        return 1

    window = MainWindow(ctx)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
