"""Visual theme: warm reading palette and Qt style sheet.

Scripture typography uses a system serif; the UI uses sans.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class TypographySettings(Protocol):
    """`Settings` fields that take part in typography."""

    theme: str
    ui_font_family: str
    ui_font_size: int
    font_family: str
    font_size: int
    content_font_family: str
    content_font_size: int


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
    success: str = "#2e7d32"
    error: str = "#c62828"
    strong: str = "#8f6bc4"
    #: Table-header band. Always darker than `panel` (the zebra rows) so the
    #: header cannot be confused with the table body.
    header: str = "#e6dfd0"


LIGHT = Palette(
    bg="#fbf9f4", panel="#f3efe6", panel_alt="#ece6d9", border="#d9d2c2",
    text="#26231d", muted="#6f685a", accent="#9a6a3a", accent_text="#ffffff",
    link="#2f5d8a", highlight="#f6e3b4", comment_bg="#f6f1e4", verse_num="#9a6a3a",
    success="#2e7d32", error="#c62828", strong="#8f6bc4",
    header="#e6dfd0",
)

DARK = Palette(
    bg="#12110f", panel="#201e1a", panel_alt="#302c25", border="#574f40",
    text="#f0e9db", muted="#b9ae9b", accent="#e0a96b", accent_text="#17130e",
    link="#9cc4e8", highlight="#6a5328", comment_bg="#2a2419", verse_num="#e0a96b",
    success="#66bb6a", error="#ef5350", strong="#b39ddb",
    header="#191713",
)


def palette(theme: str) -> Palette:
    return DARK if theme == "dark" else LIGHT


def stylesheet(theme: str, font_size: int = 13,
               font_family: str = "Noto Sans") -> str:
    """UI style sheet (``font_size`` is the UI size)."""
    p = palette(theme)
    return f"""
* {{ outline: 0; }}
QWidget {{
    background: {p.bg};
    color: {p.text};
    font-family: "{font_family}", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: {font_size}px;
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
    background: {p.panel_alt}; color: {p.text};
    border: 1px solid {p.accent};
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
QPushButton#closeButton, QToolButton#closeButton {{
    background: transparent; color: {p.muted}; border: 0;
    border-radius: 12px; font-weight: 700; font-size: 13px; padding: 0;
}}
QPushButton#closeButton:hover, QToolButton#closeButton:hover {{
    background: {p.panel_alt}; color: {p.text};
}}

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
QWidget#cmpTop {{
    background: {p.bg}; border-bottom: 0;
}}
QWidget#cmpHeader {{
    background: {p.header}; border-bottom: 1px solid {p.border};
}}
QWidget#cmpHeaderTrack {{ background: transparent; }}
QWidget#cmpPadHead {{ background: transparent; }}
QLabel#cmpChapter {{ color: {p.accent}; font-weight: 700; }}
QLabel#cmpVerseHead {{
    background: transparent; color: {p.muted}; font-weight: 700;
    border-left: 1px solid {p.border};
    padding: 3px 4px;
}}
QLabel#cmpMainHead {{
    background: {p.panel_alt}; color: {p.accent};
    border-left: 1px solid {p.border};
    font-weight: 700; padding: 3px 6px;
}}
QWidget#cmpColumnHead {{
    background: transparent; border-left: 1px solid {p.border};
}}
QComboBox#cmpCombo {{
    background: transparent; border: 1px solid transparent;
    border-radius: 4px; padding: 2px 3px; font-weight: 600;
}}
QComboBox#cmpCombo:hover, QComboBox#cmpCombo:focus {{
    background: {p.bg}; border-color: {p.border};
}}
QComboBox#cmpCombo QLineEdit {{
    background: transparent; border: 0; padding: 0; border-radius: 0;
}}
QComboBox#cmpCombo::drop-down {{
    width: 18px; border: 0; background: transparent;
}}
QComboBox#cmpCombo::down-arrow {{ width: 10px; height: 10px; }}
/* The dropdown is a floating card: a page-coloured body, an accent border and
   normal-weight rows. The combo itself stays bold and inherits nothing here;
   only the language headings keep the bold font the model gives them. */
QComboBox#cmpCombo QAbstractItemView {{
    background: {p.bg}; color: {p.text};
    border: 1px solid {p.accent}; border-radius: 6px;
    padding: 4px; outline: 0; font-weight: normal;
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QComboBox#cmpCombo QAbstractItemView::item {{
    padding: 5px 8px; border-radius: 4px;
}}
QComboBox#cmpCombo QAbstractItemView::item:selected {{
    background: {p.accent}; color: {p.accent_text};
}}
QToolButton#cmpAdd {{
    color: {p.success}; border: 1px solid {p.success};
    background: {p.panel_alt}; font-weight: 700;
}}
QToolButton#cmpAdd:hover {{ background: {p.panel}; border-color: {p.success}; }}
QToolButton#cmpAdd:disabled {{ color: {p.muted}; border-color: {p.border}; }}
QToolButton#cmpSplit {{
    color: {p.text}; border: 1px solid {p.border};
    background: {p.panel_alt}; font-weight: 700;
}}
QToolButton#cmpSplit:hover {{ border-color: {p.accent}; }}
QToolButton#cmpSplit:checked {{
    background: {p.accent}; color: {p.accent_text}; border-color: {p.accent};
}}
QToolButton#cmpSplit:disabled {{ color: {p.muted}; border-color: {p.border}; }}
QToolButton#cmpClose {{
    background: transparent; color: {p.muted}; border: 0;
    border-radius: 8px; font-weight: 700; padding: 0;
}}
QToolButton#cmpClose:hover {{ background: {p.panel_alt}; color: {p.error}; }}
QToolButton#sidebarMode {{ padding: 4px 3px; }}
QFrame#sidebarOrganizer {{
    background: {p.panel_alt}; border: 1px solid {p.border};
    border-radius: 8px;
}}
QLabel#organizerLabel {{
    color: {p.muted}; font-size: {max(9, font_size - 3)}px;
    font-weight: 700;
}}
QLabel#organizerSep {{ color: {p.muted}; padding: 0 1px; }}
QComboBox#organizerCombo, QToolButton#organizerFilter {{
    padding: 3px 6px; background: {p.panel}; color: {p.text};
    border: 1px solid {p.border}; border-radius: 5px;
    font-size: {max(9, font_size - 3)}px;
}}
QComboBox#organizerCombo:focus, QToolButton#organizerFilter:hover {{
    border-color: {p.accent};
}}
QComboBox#organizerCombo::drop-down {{ width: 12px; }}
QToolButton#organizerFilter::menu-indicator {{ subcontrol-position: right center; subcontrol-origin: padding; width: 12px; }}

QToolButton#sidebarHandle {{
    background: {p.panel}; color: {p.muted};
    border: 0; border-left: 1px solid {p.border}; border-right: 1px solid {p.border};
    border-radius: 0; padding: 0; font-size: 14px; font-weight: 700;
}}
QToolButton#sidebarHandle:hover {{ color: {p.accent_text}; background: {p.accent}; }}

QLabel#matchBadge {{
    color: {p.muted}; background: {p.panel_alt};
    border: 1px solid {p.border}; border-radius: 6px;
    padding: 1px 8px; font-size: {max(9, font_size - 3)}px;
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
/* The comparison table owns its own geometry: the document must start at the
   very left edge so its columns land on the header cells. */
QTextBrowser#cmpBrowser {{ padding: 0; }}
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
    background: {p.panel_alt}; color: {p.text};
    border: 1px solid {p.accent}; padding: 4px;
}}
QLabel#sectionTitle {{ color: {p.muted}; font-weight: 600; text-transform: uppercase;
    font-size: {max(9, font_size - 4)}px; padding: 6px 8px 2px 8px; }}
QLabel#appTitle {{ font-weight: 700; font-size: {font_size + 3}px; color: {p.text}; }}
QLabel#appSubtitle {{ color: {p.muted}; font-size: {max(9, font_size - 2)}px; }}
"""


def document_css(theme: str, font_size: int, serif_family: str,
                 content_family: str = "Noto Sans",
                 content_size: int | None = None) -> str:
    """CSS embedded in the QTextBrowsers (Qt supports a subset).

    ``font_size``/``serif_family`` control Scripture; ``content_size`` and
    ``content_family`` control body text (comments, dictionaries, notes).
    """
    p = palette(theme)
    if content_size is None:
        content_size = max(10, font_size - 2)
    return f"""
body {{ color: {p.text}; }}
p, div, li, td, th {{
    font-family: "{content_family}", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: {content_size}px;
}}
p {{ margin: 0 0 6px 0; }}
.verse {{ margin: 0 0 9px 0; line-height: 155%; }}
.verse.parallel {{ margin: 0 0 9px 0; line-height: 150%; }}
.vnum {{ color: {p.verse_num}; font-weight: 700; text-decoration: none; font-size: {font_size - 2}px; }}
.vnum:hover {{ text-decoration: underline; }}
.scripture {{ font-family: "{serif_family}", "Noto Serif", Georgia, serif; font-size: {font_size}px; }}
.chapter-title {{ color: {p.accent}; font-family: "{serif_family}", Georgia, serif;
    font-size: {font_size + 8}px; font-weight: 700; margin: 2px 0 14px 0; }}
.comment {{ background: {p.comment_bg}; border-left: 3px solid {p.accent};
    margin: 2px 0 12px 22px; padding: 7px 12px; font-size: {max(10, content_size - 1)}px;
    color: {p.text}; }}
.comment .ctag {{ color: {p.muted}; font-size: {max(9, content_size - 4)}px;
    font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
.comment a {{ color: {p.link}; }}
.muted {{ color: {p.muted}; }}
.hit {{ margin: 0 0 10px 0; }}
.hit .meta {{ color: {p.muted}; font-size: {max(9, content_size - 2)}px; }}
.hit a {{ color: {p.link}; text-decoration: none; }}
.group {{ color: {p.accent}; font-weight: 700; font-size: {max(10, content_size + 1)}px;
    margin: 16px 0 8px 0; }}
b {{ color: {p.text}; }}
a {{ color: {p.link}; }}
a.strong {{ color: {p.strong}; font-size: 82%; text-decoration: none; font-weight: 600; }}
a.strong:hover {{ text-decoration: underline; }}
.entry-title {{ color: {p.accent}; font-family: "{serif_family}", Georgia, serif;
    font-size: {font_size + 4}px; font-weight: 700; margin-bottom: 10px; }}
.cmp-table {{ border-collapse: collapse; margin: 0; }}
.cmp-table td {{
    border-left: 1px solid {p.border};
    border-right: 1px solid {p.border};
    border-bottom: 1px solid {p.border};
    padding: 3px 5px; vertical-align: top;
}}
.cmp-verse {{
    color: {p.verse_num}; text-align: center; vertical-align: middle;
    font-weight: 700;
}}
.cmp-verse a {{ color: {p.verse_num}; text-decoration: none; }}
.cmp-row-alt {{ background-color: {p.panel}; }}
.cmp-count {{
    color: {p.accent}; font-size: {max(9, content_size - 3)}px;
    font-weight: 700; margin-right: 4px;
}}
.cmp-src {{ margin: 0 0 4px 0; }}
.cmp-heading {{
    color: {p.accent}; font-family: "{serif_family}", Georgia, serif;
    font-weight: 700; text-align: center;
    margin: 2px 0 6px 0; font-size: {max(10, content_size + 1)}px;
}}
.cmp-draft {{ color: {p.muted}; }}
.cmp-missing, .cmp-empty {{ color: {p.muted}; }}
.cmp-warning {{ margin: 0 0 8px 0; }}
"""


def ui_stylesheet(settings: TypographySettings) -> str:
    """Qt style sheet with the typography chosen for the UI."""
    return stylesheet(settings.theme, settings.ui_font_size,
                      settings.ui_font_family)


def document_css_for(settings: TypographySettings) -> str:
    """Viewer CSS with the current typography preferences."""
    return document_css(
        settings.theme,
        settings.font_size,
        settings.font_family,
        content_family=settings.content_font_family,
        content_size=settings.content_font_size,
    )
