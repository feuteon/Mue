"""Palette et feuille de style Qt (thème sombre, accent irisé menthe -> violet)."""

from __future__ import annotations

import sys

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QFont, QLinearGradient

BG = "#111116"
CARD = "#18181F"
CARD_HI = "#1F1F28"
BORDER = "#2A2A36"
TEXT = "#ECECF2"
MUTED = "#8C8C9E"
FAINT = "#5B5B6B"
MINT = "#7CF7C6"
VIOLET = "#8E7CFF"
PINK = "#FF8BC8"
OK = "#5BE3A0"
ERR = "#FF6B7A"

FONT_FAMILY = "Segoe UI Variable Text" if sys.platform == "win32" else "Inter"
FALLBACKS = ["Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Sans Serif"]

CATEGORY_COLORS = {
    "image": "#7CF7C6", "gif": "#7CF7C6", "svg": "#7CF7C6", "raw": "#7CF7C6",
    "video": "#8E7CFF", "audio": "#FFB86B", "pdf": "#FF6B7A", "ebook": "#FF8BC8",
    "word": "#6BB8FF", "sheet": "#5BE3A0", "csv": "#5BE3A0", "json": "#E6D86B", "slides": "#FF9F6B",
}


def stylesheet() -> str:
    from .widgets import asset
    return QSS.replace("{ARROW}", asset("chevron.png").as_posix())


def font(size: float = 10, weight: int = QFont.Normal) -> QFont:
    f = QFont(FONT_FAMILY)
    if hasattr(f, "setFamilies"):
        f.setFamilies([FONT_FAMILY, *FALLBACKS])
    f.setPointSizeF(size)
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def accent_gradient(x0: float, y0: float, x1: float, y1: float) -> QLinearGradient:
    g = QLinearGradient(QPointF(x0, y0), QPointF(x1, y1))
    g.setColorAt(0.0, QColor(MINT))
    g.setColorAt(0.65, QColor(VIOLET))
    g.setColorAt(1.0, QColor(PINK))
    return g


QSS = f"""
* {{ color: {TEXT}; }}
QWidget#Root {{ background: {BG}; }}
QLabel {{ background: transparent; }}
QLabel[muted="true"] {{ color: {MUTED}; }}
QLabel[faint="true"] {{ color: {FAINT}; }}
QLabel[h2="true"] {{ font-weight: 600; }}

QFrame#Card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 14px; }}

QPushButton {{
    background: {CARD_HI}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 7px 14px; color: {TEXT};
}}
QPushButton:hover {{ background: #272733; border-color: #3A3A4A; }}
QPushButton:pressed {{ background: #2E2E3C; }}
QPushButton:disabled {{ color: {FAINT}; background: {CARD}; }}
QPushButton[primary="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {MINT}, stop:0.7 {VIOLET}, stop:1 {PINK});
    color: #0E0E14; border: none; font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #95FAD3, stop:0.7 #A194FF, stop:1 #FFA3D4);
}}
QPushButton[flat="true"] {{ background: transparent; border: none; padding: 4px 8px; color: {MUTED}; }}
QPushButton[flat="true"]:hover {{ color: {TEXT}; background: #ffffff10; }}
QPushButton[danger="true"]:hover {{ color: {ERR}; border-color: {ERR}; }}

QComboBox, QSpinBox, QLineEdit {{
    background: {BG}; border: 1px solid {BORDER}; border-radius: 8px; padding: 5px 9px;
    min-height: 20px; selection-background-color: {VIOLET};
}}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: #3C3C4E; }}
QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {VIOLET}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{{ARROW}}"); width: 10px; height: 10px; margin-right: 8px; }}
QComboBox QAbstractItemView {{ background: {CARD_HI}; border: 1px solid {BORDER}; outline: none;
    selection-background-color: #8E7CFF40; padding: 4px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}


QSlider::groove:horizontal {{ height: 4px; background: #2A2A36; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {MINT}, stop:1 {VIOLET});
    border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #34344A; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #45455E; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QToolTip {{ background: {CARD_HI}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; border-radius: 6px; }}
"""
