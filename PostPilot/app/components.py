"""Reusable UI components for PostPilot v1.

Provides cards, status badges, collapsible accordions, platform chips,
and standardized button variants adhering to the design system.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme

# Platform display configuration
PLATFORM_META = {
    "tiktok": {"name": "TikTok", "icon": "♬", "color": "#00F2FE", "bg": "rgba(0, 242, 254, 0.12)"},
    "youtube": {"name": "YouTube", "icon": "▶", "color": "#FF4E4E", "bg": "rgba(255, 78, 78, 0.12)"},
    "instagram": {"name": "Instagram", "icon": "📷", "color": "#F472B6", "bg": "rgba(244, 114, 182, 0.12)"},
    "facebook": {"name": "Facebook", "icon": "f", "color": "#3B82F6", "bg": "rgba(59, 130, 246, 0.12)"},
}

STATUS_STYLES = {
    "success": {"color": theme.STATUS_SUCCESS, "bg": theme.STATUS_SUCCESS_BG, "border": theme.STATUS_SUCCESS_BORDER},
    "ready": {"color": theme.STATUS_SUCCESS, "bg": theme.STATUS_SUCCESS_BG, "border": theme.STATUS_SUCCESS_BORDER},
    "done": {"color": theme.STATUS_SUCCESS, "bg": theme.STATUS_SUCCESS_BG, "border": theme.STATUS_SUCCESS_BORDER},
    "open": {"color": theme.STATUS_SUCCESS, "bg": theme.STATUS_SUCCESS_BG, "border": theme.STATUS_SUCCESS_BORDER},

    "warning": {"color": theme.STATUS_WARNING, "bg": theme.STATUS_WARNING_BG, "border": theme.STATUS_WARNING_BORDER},
    "uploading": {"color": theme.STATUS_WARNING, "bg": theme.STATUS_WARNING_BG, "border": theme.STATUS_WARNING_BORDER},
    "running": {"color": theme.STATUS_WARNING, "bg": theme.STATUS_WARNING_BG, "border": theme.STATUS_WARNING_BORDER},

    "danger": {"color": theme.STATUS_DANGER, "bg": theme.STATUS_DANGER_BG, "border": theme.STATUS_DANGER_BORDER},
    "failed": {"color": theme.STATUS_DANGER, "bg": theme.STATUS_DANGER_BG, "border": theme.STATUS_DANGER_BORDER},
    "error": {"color": theme.STATUS_DANGER, "bg": theme.STATUS_DANGER_BG, "border": theme.STATUS_DANGER_BORDER},

    "info": {"color": theme.STATUS_INFO, "bg": theme.STATUS_INFO_BG, "border": theme.STATUS_INFO_BORDER},
    "scheduled": {"color": theme.STATUS_INFO, "bg": theme.STATUS_INFO_BG, "border": theme.STATUS_INFO_BORDER},

    "neutral": {"color": theme.STATUS_NEUTRAL, "bg": theme.STATUS_NEUTRAL_BG, "border": theme.STATUS_NEUTRAL_BORDER},
    "pending": {"color": theme.STATUS_NEUTRAL, "bg": theme.STATUS_NEUTRAL_BG, "border": theme.STATUS_NEUTRAL_BORDER},
    "closed": {"color": theme.STATUS_NEUTRAL, "bg": theme.STATUS_NEUTRAL_BG, "border": theme.STATUS_NEUTRAL_BORDER},
    "stopped": {"color": theme.STATUS_NEUTRAL, "bg": theme.STATUS_NEUTRAL_BG, "border": theme.STATUS_NEUTRAL_BORDER},
    "skipped": {"color": theme.STATUS_NEUTRAL, "bg": theme.STATUS_NEUTRAL_BG, "border": theme.STATUS_NEUTRAL_BORDER},
}


class Card(QFrame):
    """Main card container with subtle border and rounded corners."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#card, Card {{
                background-color: {theme.BG_SURFACE};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 10px;
            }}
        """)


class CardAlt(QFrame):
    """Nested or alternate card container."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cardAlt")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            QFrame#cardAlt, CardAlt {{
                background-color: {theme.BG_SURFACE_ALT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)


class Badge(QFrame):
    """Modern status pill badge with status dot and custom tint."""

    def __init__(self, text: str, status: str = "neutral", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 3, 8, 3)
        self._layout.setSpacing(5)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(10)
        self._label = QLabel(text)
        self._label.setStyleSheet("font-size: 11px; font-weight: 600;")

        self._layout.addWidget(self._dot)
        self._layout.addWidget(self._label)
        self.set_status(status, text)

    def set_status(self, status: str, text: str | None = None) -> None:
        style = STATUS_STYLES.get(status.lower(), STATUS_STYLES["neutral"])
        color = style["color"]
        bg = style["bg"]
        border = style["border"]

        self.setStyleSheet(f"""
            Badge {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 11px;
            }}
        """)
        self._dot.setStyleSheet(f"color: {color}; font-size: 8px; background: transparent;")
        self._label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 600; background: transparent;")
        if text is not None:
            self._label.setText(text)

    def text(self) -> str:
        return self._label.text()


class PlatformChip(QFrame):
    """Branded platform badge chip."""

    def __init__(self, platform: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        meta = PLATFORM_META.get(platform.lower(), {
            "name": platform.capitalize(),
            "icon": "●",
            "color": theme.TEXT_PRIMARY,
            "bg": theme.BG_SURFACE_ALT,
        })
        self._color = meta["color"]
        self._bg = meta["bg"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 10, 4)
        layout.setSpacing(6)

        icon_lbl = QLabel(meta["icon"])
        icon_lbl.setStyleSheet(f"color: {self._color}; font-size: 12px; font-weight: bold; background: transparent;")
        layout.addWidget(icon_lbl)

        name_lbl = QLabel(meta["name"])
        name_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(name_lbl)

        self.setStyleSheet(f"""
            PlatformChip {{
                background-color: {self._bg};
                border: 1px solid {self._color}50;
                border-radius: 6px;
            }}
        """)


class PrimaryButton(QPushButton):
    """Styled primary action button."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("primaryBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SecondaryButton(QPushButton):
    """Styled secondary action button."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("secondaryBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class DangerButton(QPushButton):
    """Styled danger action button."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("dangerBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class GhostButton(QPushButton):
    """Styled ghost action button."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("ghostBtn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class CollapsibleBox(QWidget):
    """Clean collapsible section with chevron toggle and smooth show/hide."""

    toggled = Signal(bool)

    def __init__(self, title: str = "Proxy Settings", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._is_expanded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self.toggle_btn = QPushButton(f"▶  {self._title}")
        self.toggle_btn.setObjectName("ghostBtn")
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 6px 10px;
                color: {theme.TEXT_SECONDARY};
                font-weight: 600;
                font-size: 12px;
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 6px;
                background-color: {theme.BG_SURFACE_ALT};
            }}
            QPushButton:hover {{
                color: {theme.TEXT_PRIMARY};
                border-color: {theme.BORDER_STRONG};
            }}
        """)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self._on_toggle)
        layout.addWidget(self.toggle_btn)

        self.content_area = QWidget()
        self.content_area.setVisible(False)
        layout.addWidget(self.content_area)

    def set_content_layout(self, content_layout) -> None:
        self.content_area.setLayout(content_layout)

    def _on_toggle(self) -> None:
        self.set_expanded(not self._is_expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._is_expanded = expanded
        self.content_area.setVisible(expanded)
        arrow = "▼" if expanded else "▶"
        self.toggle_btn.setText(f"{arrow}  {self._title}")
        self.toggled.emit(expanded)

    def is_expanded(self) -> bool:
        return self._is_expanded


class SectionHeader(QWidget):
    """Header bar with title, subtitle, and optional right-aligned action widget."""

    def __init__(self, title: str, subtitle: str = "", action_widget: QWidget | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("sectionTitle")
        text_layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName("sectionSubtitle")
            text_layout.addWidget(sub_lbl)

        layout.addLayout(text_layout)
        layout.addStretch(1)

        if action_widget is not None:
            layout.addWidget(action_widget)
