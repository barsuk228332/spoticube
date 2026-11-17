"""Тёмная тема оформления."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#3ddc84"
ACCENT_DIM = "#2fb46c"
BG = "#0e1116"
PANEL = "#151a22"
CARD = "#1a212b"
BORDER = "#242c38"
TEXT = "#e6edf3"
MUTED = "#8b98a9"

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "Inter", "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog, QWidget#Root, QSplitter {{ background: {BG}; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

QFrame#Panel, QWidget#Panel {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}

QLineEdit {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 12px;
    selection-background-color: {ACCENT_DIM};
    color: {TEXT};
}}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}

QPushButton {{
    background: #212936;
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: #28313f; border-color: #33405080; }}
QPushButton:pressed {{ background: #1c2431; }}
QPushButton:disabled {{ color: #5b6674; background: #171d26; }}

QPushButton#Primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: #07130c;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: #4de894; border-color: #4de894; }}
QPushButton#Primary:disabled {{ background: #2c4638; border-color: #2c4638; color: #7d9c8b; }}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid transparent;
    padding: 6px 10px;
    color: {MUTED};
}}
QPushButton#Ghost:hover {{ color: {TEXT}; border-color: {BORDER}; }}

QPushButton#Danger {{
    background: transparent;
    border: 1px solid #503038;
    color: #f08a94;
    padding: 5px 10px;
}}
QPushButton#Danger:hover {{ background: #2a1a1f; }}

QComboBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 9px;
    padding: 8px 12px;
    min-width: 110px;
}}
QComboBox:hover {{ border-color: #334050; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_DIM};
    selection-color: #07130c;
    outline: none;
}}

QListWidget#Results {{
    background: transparent;
    border: none;
    outline: none;
}}
QListWidget#Results::item {{
    background: transparent;
    border: none;
}}

QFrame#ResultCard {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
}}
QFrame#ResultCard:hover {{ border-color: #38465a; background: #1d2530; }}
QFrame#ResultCard[selected="true"] {{
    border: 1px solid {ACCENT};
    background: #1b2a24;
}}

QLabel#Thumb {{
    background: #10151c;
    border-radius: 8px;
    color: #4b5766;
}}
QLabel#CardTitle {{ font-size: 13px; font-weight: 600; color: {TEXT}; }}
QLabel#CardMeta {{ font-size: 11px; color: {MUTED}; }}

QLabel#PreviewTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#PreviewMeta {{ font-size: 12px; color: {MUTED}; }}
QLabel#SectionTitle {{
    font-size: 12px;
    font-weight: 700;
    color: {MUTED};
    letter-spacing: 1px;
}}
QLabel#Hint {{ color: {MUTED}; font-size: 12px; }}

QProgressBar {{
    background: #121821;
    border: none;
    border-radius: 5px;
    height: 9px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 5px;
}}

QListWidget#Downloads {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 6px;
    outline: none;
}}
QListWidget#Downloads::item {{ border: none; }}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2c3644;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: #3a4656; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

QSplitter::handle {{ background: transparent; }}
QSplitter::handle:vertical {{ height: 10px; }}

QStatusBar {{ color: {MUTED}; background: {PANEL}; }}
QToolTip {{
    background: {PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    padding: 5px 8px;
    border-radius: 6px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(CARD))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(CARD))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_DIM))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#07130c"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
