"""Central styling source of truth for PostPilot v1.

Linear / Stripe-inspired modern dark theme with refined typography,
card surfaces, subtle borders, and harmonious platform accents.
"""

from __future__ import annotations

import os

# =====================================================================
# Color Tokens
# =====================================================================

# Surfaces & Backgrounds
BG_BASE = "#080B11"           # Deep canvas obsidian
BG_SURFACE = "#111622"        # Main card & panel surface
BG_SURFACE_ALT = "#161D2C"    # Elevated elements, nested cards
BG_INPUT = "#0A0E17"          # Crisp deep inset input fields
BG_HOVER = "#1C2538"          # Interactive hover state
BG_ACTIVE = "#243048"         # Pressed / active state

# Borders
BORDER_SUBTLE = "#1C2537"     # Card & divider borders
BORDER_STRONG = "#2A374F"     # Input borders, card headers
BORDER_FOCUS = "#3B82F6"      # Focus ring blue

# Text
TEXT_PRIMARY = "#F8FAFC"      # Pure high-contrast white
TEXT_SECONDARY = "#94A3B8"    # Subtle secondary slate
TEXT_MUTED = "#64748B"        # Dim labels, placeholders
TEXT_DISABLED = "#475569"

# Brand & Status Accents
ACCENT_PRIMARY = "#3B82F6"    # Electric Blue (actions)
ACCENT_PRIMARY_HOVER = "#2563EB"
ACCENT_PRIMARY_ACTIVE = "#1D4ED8"

STATUS_SUCCESS = "#10B981"    # Emerald green (ready, done)
STATUS_SUCCESS_BG = "rgba(16, 185, 129, 0.14)"
STATUS_SUCCESS_BORDER = "rgba(16, 185, 129, 0.35)"

STATUS_WARNING = "#F59E0B"    # Amber (uploading, running)
STATUS_WARNING_BG = "rgba(245, 158, 11, 0.14)"
STATUS_WARNING_BORDER = "rgba(245, 158, 11, 0.35)"

STATUS_DANGER = "#EF4444"     # Rose red (failed, error)
STATUS_DANGER_BG = "rgba(239, 68, 68, 0.14)"
STATUS_DANGER_BORDER = "rgba(239, 68, 68, 0.35)"

STATUS_INFO = "#38BDF8"       # Sky blue (scheduled, info)
STATUS_INFO_BG = "rgba(56, 189, 248, 0.14)"
STATUS_INFO_BORDER = "rgba(56, 189, 248, 0.35)"

STATUS_NEUTRAL = "#64748B"    # Muted gray (pending, closed)
STATUS_NEUTRAL_BG = "rgba(100, 116, 139, 0.14)"
STATUS_NEUTRAL_BORDER = "rgba(100, 116, 139, 0.35)"

# Platform Brand Colors
PLATFORM_COLORS = {
    "tiktok": {"color": "#00F2FE", "bg": "rgba(0, 242, 254, 0.12)", "border": "rgba(0, 242, 254, 0.35)"},
    "youtube": {"color": "#FF4E4E", "bg": "rgba(255, 78, 78, 0.12)", "border": "rgba(255, 78, 78, 0.35)"},
    "instagram": {"color": "#F472B6", "bg": "rgba(244, 114, 182, 0.12)", "border": "rgba(244, 114, 182, 0.35)"},
    "facebook": {"color": "#3B82F6", "bg": "rgba(59, 130, 246, 0.12)", "border": "rgba(59, 130, 246, 0.35)"},
}

# =====================================================================
# Complete Application Stylesheet (QSS)
# =====================================================================

def _ensure_check_asset(asset_path: str) -> None:
    if os.path.exists(asset_path):
        return
    try:
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtGui import QColor, QImage, QPainter, QPen

        os.makedirs(os.path.dirname(asset_path), exist_ok=True)
        img = QImage(16, 16, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FFFFFF"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(QPoint(3, 8), QPoint(6, 12))
        p.drawLine(QPoint(6, 12), QPoint(13, 4))
        p.end()
        img.save(asset_path)
    except Exception:
        pass


def get_application_stylesheet() -> str:
    """Generate the complete, modern dark-theme QSS stylesheet."""
    check_img = os.path.join(os.path.dirname(__file__), "assets", "check.png").replace("\\", "/")
    _ensure_check_asset(check_img)
    return f"""
/* ------------------------------------------------------------- Global */
QMainWindow, #centralWidget, QDialog {{
    background-color: {BG_BASE};
}}

QWidget {{
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', -apple-system, 'Inter', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    selection-background-color: {ACCENT_PRIMARY};
    selection-color: #FFFFFF;
}}

/* -------------------------------------------------------- Scroll Areas */
QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background-color: {BG_BASE};
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 0 4px 0;
}}

QScrollBar::handle:vertical {{
    background: {BORDER_STRONG};
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0 4px 0 4px;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER_STRONG};
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ------------------------------------------------------------- Tabs */
QTabWidget::pane {{
    border: 1px solid {BORDER_SUBTLE};
    background-color: {BG_BASE};
    border-radius: 8px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    padding: 10px 22px;
    margin-right: 4px;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    border: 1px solid {BORDER_SUBTLE};
    border-bottom: none;
    font-weight: 600;
    font-size: 13px;
}}

QTabBar::tab:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
}}

QTabBar::tab:selected {{
    background-color: {BG_BASE};
    color: {ACCENT_PRIMARY};
    border-color: {BORDER_SUBTLE};
    border-top: 2px solid {ACCENT_PRIMARY};
}}

/* ----------------------------------------------------- Splitter & Dock */
QSplitter::handle {{
    background-color: {BORDER_SUBTLE};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QDockWidget {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
    font-size: 12px;
}}

QDockWidget::title {{
    background-color: {BG_SURFACE};
    padding: 8px 12px;
    border-top: 1px solid {BORDER_SUBTLE};
    border-bottom: 1px solid {BORDER_SUBTLE};
    color: {TEXT_SECONDARY};
}}

/* ------------------------------------------------ Form & Input Widgets */
QLineEdit, QSpinBox, QDateTimeEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 7px 11px;
    font-size: 13px;
    selection-background-color: {ACCENT_PRIMARY};
}}

QLineEdit:focus, QSpinBox:focus, QDateTimeEdit:focus {{
    border: 1px solid {BORDER_FOCUS};
    background-color: {BG_SURFACE};
}}

QLineEdit:disabled, QSpinBox:disabled, QDateTimeEdit:disabled {{
    background-color: {BG_BASE};
    color: {TEXT_DISABLED};
    border-color: {BORDER_SUBTLE};
}}

QComboBox {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 7px 11px;
    padding-right: 28px;
    font-size: 13px;
}}

QComboBox:hover {{
    border-color: {TEXT_MUTED};
}}

QComboBox:focus {{
    border: 1px solid {BORDER_FOCUS};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {BORDER_SUBTLE};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}

QComboBox::down-arrow {{
    width: 6px;
    height: 6px;
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_SECONDARY};
    margin-right: 6px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 4px;
    selection-background-color: {ACCENT_PRIMARY};
    outline: none;
}}

/* Spinbox & DateTime Arrows */
QSpinBox::up-button, QSpinBox::down-button,
QDateTimeEdit::up-button, QDateTimeEdit::down-button {{
    width: 18px;
    background: transparent;
    border: none;
}}

QSpinBox::up-arrow, QDateTimeEdit::up-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 4px solid {TEXT_SECONDARY};
}}

QSpinBox::down-arrow, QDateTimeEdit::down-arrow {{
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid {TEXT_SECONDARY};
}}

/* Calendar Popup */
QCalendarWidget QWidget {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
}}

QCalendarWidget QToolButton {{
    color: {TEXT_PRIMARY};
    background-color: transparent;
    border-radius: 4px;
    padding: 4px 8px;
    font-weight: 600;
}}

QCalendarWidget QToolButton:hover {{
    background-color: {BG_HOVER};
}}

QCalendarWidget QMenu {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
}}

QCalendarWidget QSpinBox {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER_STRONG};
}}

/* ------------------------------------------------------------- Buttons */
QPushButton {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {TEXT_MUTED};
}}

QPushButton:pressed {{
    background-color: {BG_ACTIVE};
}}

QPushButton:disabled {{
    background-color: {BG_BASE};
    color: {TEXT_DISABLED};
    border-color: {BORDER_SUBTLE};
}}

QPushButton#primaryBtn {{
    background-color: {ACCENT_PRIMARY};
    color: #FFFFFF;
    border: 1px solid {ACCENT_PRIMARY_HOVER};
    font-weight: 600;
}}

QPushButton#primaryBtn:hover {{
    background-color: {ACCENT_PRIMARY_HOVER};
}}

QPushButton#primaryBtn:pressed {{
    background-color: {ACCENT_PRIMARY_ACTIVE};
}}

QPushButton#secondaryBtn {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
}}

QPushButton#secondaryBtn:hover {{
    background-color: {BG_HOVER};
    border-color: {TEXT_SECONDARY};
}}

QPushButton#dangerBtn {{
    background-color: {STATUS_DANGER_BG};
    color: {STATUS_DANGER};
    border: 1px solid {STATUS_DANGER_BORDER};
    font-weight: 600;
}}

QPushButton#dangerBtn:hover {{
    background-color: {STATUS_DANGER};
    color: #FFFFFF;
    border-color: {STATUS_DANGER};
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: 1px solid transparent;
}}

QPushButton#ghostBtn:hover {{
    background-color: {BG_HOVER};
    color: {TEXT_PRIMARY};
    border-color: {BORDER_SUBTLE};
}}

/* ------------------------------------------------------------ Checkbox */
QCheckBox {{
    color: {TEXT_PRIMARY};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid {BORDER_STRONG};
    border-radius: 4px;
    background-color: {BG_INPUT};
}}

QCheckBox::indicator:hover {{
    border-color: {BORDER_FOCUS};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT_PRIMARY};
    border: 1px solid {BORDER_FOCUS};
    image: url('{check_img}');
}}

/* --------------------------------------------------------- List Widget */
QListWidget {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    padding: 6px;
    outline: none;
}}

QListWidget::item {{
    padding: 6px 8px;
    border-radius: 6px;
    margin-bottom: 4px;
    color: {TEXT_PRIMARY};
    border: 1px solid transparent;
}}

QListWidget::item:hover {{
    background-color: {BG_HOVER};
}}

QListWidget::item:selected {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_STRONG};
    color: #FFFFFF;
}}

/* ------------------------------------------------------------- Tooltip */
QToolTip {{
    background-color: {BG_SURFACE_ALT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ---------------------------------------------------------- Text Edit */
QTextEdit {{
    background-color: {BG_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 6px;
    padding: 8px;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 12px;
}}

/* ------------------------------------------------- Custom Object Names */
QFrame#card, #card {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 10px;
}}

QFrame#cardAlt, #cardAlt {{
    background-color: {BG_SURFACE_ALT};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
}}

#cardHeader {{
    font-weight: 600;
    font-size: 15px;
    color: {TEXT_PRIMARY};
}}

#sectionTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

#sectionSubtitle {{
    font-size: 12px;
    color: {TEXT_MUTED};
}}

#terminalView {{
    background-color: #07090E;
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
    font-size: 12px;
    padding: 8px;
}}
"""
