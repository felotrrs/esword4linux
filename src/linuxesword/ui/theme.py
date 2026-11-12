"""Tema visual: paleta cálida de lectura y hoja de estilo Qt.

La tipografía de Escritura usa una serif de sistema; la UI usa sans.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    bg: str
    panel: str
    panel_alt: str
    border: str
    text: str
    muted: str
    accent: str
    accent_text: str
    link: str
    highlight: str
    comment_bg: str
    verse_num: str


LIGHT = Palette(
    bg="#fbf9f4", panel="#f3efe6", panel_alt="#ece6d9", border="#d9d2c2",
    text="#26231d", muted="#6f685a", accent="#9a6a3a", accent_text="#ffffff",
    link="#2f5d8a", highlight="#f6e3b4", comment_bg="#f6f1e4", verse_num="#9a6a3a",
)

DARK = Palette(
    bg="#12110f", panel="#201e1a", panel_alt="#302c25", border="#574f40",
    text="#f0e9db", muted="#b9ae9b", accent="#e0a96b", accent_text="#17130e",
    link="#9cc4e8", highlight="#6a5328", comment_bg="#2a2419", verse_num="#e0a96b",
)


def palette(theme: str) -> Palette:
    return DARK if theme == "dark" else LIGHT


def stylesheet(theme: str, font_size: int = 15) -> str:
    p = palette(theme)
    return f"""
* {{ outline: 0; }}
QWidget {{
    background: {p.bg};
    color: {p.text};
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: {font_size - 2}px;
}}
QMainWindow, QDialog {{ background: {p.bg}; }}

QMenuBar {{ background: {p.panel}; border-bottom: 1px solid {p.border}; }}
QMenuBar::item {{ padding: 6px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {p.panel_alt}; border-radius: 4px; }}
QMenu {{ background: {p.panel}; border: 1px solid {p.border}; padding: 4px; }}
QMenu::item {{ padding: 6px 24px 6px 18px; border-radius: 4px; }}
QMenu::item:selected {{ background: {p.accent}; color: {p.accent_text}; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 8px; }}

QToolBar {{ background: {p.panel}; border: 0; border-bottom: 1px solid {p.border}; spacing: 6px; padding: 5px; }}
QStatusBar {{ background: {p.panel}; border-top: 1px solid {p.border}; color: {p.muted}; }}
QStatusBar QLabel {{ color: {p.muted}; padding: 0 4px; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {p.panel}; color: {p.text};
    border: 1px solid {p.border}; border-radius: 6px;
    padding: 5px 8px; selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {p.accent}; }}
QComboBox::drop-down {{ border: 0; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {p.panel}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}

QPushButton {{
    background: {p.panel_alt}; border: 1px solid {p.border};
    border-radius: 6px; padding: 6px 12px;
}}
QPushButton:hover {{ border-color: {p.accent}; }}
QPushButton:pressed {{ background: {p.border}; }}
QPushButton#primary {{ background: {p.accent}; color: {p.accent_text}; border: 0; }}
QPushButton#primary:hover {{ background: {p.accent}; }}

QCheckBox {{ spacing: 6px; }}

QTabWidget::pane {{ border: 0; background: {p.bg}; }}
QTabBar::tab {{
    background: {p.panel}; color: {p.muted}; padding: 7px 16px;
    border: 1px solid {p.border}; border-bottom: 0;
    border-top-left-radius: 7px; border-top-right-radius: 7px; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {p.bg}; color: {p.text}; border-bottom: 2px solid {p.accent}; }}
QTabBar::tab:hover {{ color: {p.text}; }}
QTabBar::close-button {{ subcontrol-position: right; }}

QToolButton {{
    background: {p.panel_alt}; border: 1px solid {p.border};
    border-radius: 6px; padding: 5px 10px;
}}
QToolButton:hover {{ border-color: {p.accent}; }}
QToolButton:checked {{ background: {p.accent}; color: {p.accent_text}; border-color: {p.accent}; }}
QToolButton#sidebarMode, QToolButton#organizerFilter {{ padding: 4px 3px; }}
QFrame#sidebarOrganizer {{
    background: {p.panel_alt}; border: 1px solid {p.border};
    border-radius: 8px;
}}
QLabel#organizerLabel {{
    color: {p.muted}; font-size: {max(9, font_size - 5)}px;
    font-weight: 700;
}}
QLabel#organizerSep {{ color: {p.muted}; padding: 0 1px; }}
QComboBox#organizerCombo {{
    padding: 2px 2px; background: {p.panel}; border-radius: 5px;
    font-size: {max(9, font_size - 5)}px;
}}
QComboBox#organizerCombo::drop-down {{ width: 12px; }}
QToolButton#organizerFilter {{ font-size: {max(9, font_size - 4)}px; }}

QToolButton#sidebarHandle {{
    background: {p.panel}; color: {p.muted};
    border: 0; border-left: 1px solid {p.border}; border-right: 1px solid {p.border};
    border-radius: 0; padding: 0; font-size: 14px; font-weight: 700;
}}
QToolButton#sidebarHandle:hover {{ color: {p.accent_text}; background: {p.accent}; }}

QLabel#matchBadge {{
    color: {p.muted}; background: {p.panel_alt};
    border: 1px solid {p.border}; border-radius: 6px;
    padding: 1px 8px; font-size: {max(9, font_size - 5)}px;
}}
QLabel#strongBadge {{ color: {p.accent_text}; background: {p.accent};
    border-radius: 6px; padding: 1px 8px; font-weight: 700; }}

QTreeWidget, QListWidget {{
    background: {p.panel}; border: 0; border-right: 1px solid {p.border};
    padding: 4px; alternate-background-color: {p.panel_alt};
}}
QTreeWidget::item, QListWidget::item {{ padding: 4px 2px; border-radius: 4px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {p.accent}; color: {p.accent_text};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{ background: {p.panel_alt}; }}
QHeaderView::section {{ background: {p.panel}; border: 0; padding: 4px; }}

QTextBrowser {{
    background: {p.bg}; border: 0; padding: 8px 18px;
    selection-background-color: {p.highlight}; selection-color: {p.text};
}}
QSplitter::handle {{ background: {p.border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QProgressBar {{
    background: {p.panel_alt}; border: 0; border-radius: 3px;
    height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 3px; }}

QScrollBar:vertical {{ background: transparent; width: 11px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.accent}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 11px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}

QToolTip {{
    background: {p.panel}; color: {p.text};
    border: 1px solid {p.border}; padding: 4px;
}}
QLabel#sectionTitle {{ color: {p.muted}; font-weight: 600; text-transform: uppercase;
    font-size: {max(9, font_size - 6)}px; padding: 6px 8px 2px 8px; }}
QLabel#appTitle {{ font-weight: 700; font-size: {font_size + 1}px; color: {p.text}; }}
QLabel#appSubtitle {{ color: {p.muted}; font-size: {max(9, font_size - 4)}px; }}
"""


def document_css(theme: str, font_size: int, serif_family: str) -> str:
    """CSS embebido en los QTextBrowser (Qt soporta un subconjunto)."""
    p = palette(theme)
    return f"""
body {{ color: {p.text}; }}
p {{ margin: 0 0 6px 0; }}
.verse {{ margin: 0 0 9px 0; line-height: 155%; }}
.verse.parallel {{ margin: 0 0 9px 0; line-height: 150%; }}
.vnum {{ color: {p.verse_num}; font-weight: 700; text-decoration: none; font-size: {font_size - 2}px; }}
.vnum:hover {{ text-decoration: underline; }}
.scripture {{ font-family: "{serif_family}", "Noto Serif", Georgia, serif; font-size: {font_size}px; }}
.chapter-title {{ color: {p.accent}; font-family: "{serif_family}", Georgia, serif;
    font-size: {font_size + 8}px; font-weight: 700; margin: 2px 0 14px 0; }}
.comment {{ background: {p.comment_bg}; border-left: 3px solid {p.accent};
    margin: 2px 0 12px 22px; padding: 7px 12px; font-size: {max(10, font_size - 3)}px;
    color: {p.text}; }}
.comment .ctag {{ color: {p.muted}; font-size: {max(9, font_size - 5)}px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
.comment a {{ color: {p.link}; }}
.muted {{ color: {p.muted}; }}
.hit {{ margin: 0 0 10px 0; }}
.hit .meta {{ color: {p.muted}; font-size: {max(9, font_size - 4)}px; }}
.hit a {{ color: {p.link}; text-decoration: none; }}
.group {{ color: {p.accent}; font-weight: 700; font-size: {max(10, font_size - 1)}px;
    margin: 16px 0 8px 0; }}
b {{ color: {p.text}; }}
a {{ color: {p.link}; }}
.entry-title {{ color: {p.accent}; font-family: "{serif_family}", Georgia, serif;
    font-size: {font_size + 4}px; font-weight: 700; margin-bottom: 10px; }}
"""
