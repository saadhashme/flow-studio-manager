"""Upload Queue tab: lists incoming videos and controls per-platform uploads.

Linear/Stripe-inspired dashboard with visual thumbnail cards, platform chips,
per-target live status badges, active upload progress indicators, failure callouts,
and post/schedule/skip controls.
"""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QDateTime, Qt, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateTimeEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from accounts import PLATFORMS
from . import theme
from .components import (
    Badge,
    Card,
    CardAlt,
    DangerButton,
    GhostButton,
    PlatformChip,
    PrimaryButton,
    SecondaryButton,
    SectionHeader,
)

log = logging.getLogger(__name__)


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%H:%M")
    except Exception:
        return "??:??"


class _QueueItemWidget(QFrame):
    """Custom widget rendered inside each list item in the queue list."""

    def __init__(self, item: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: transparent; border: none;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # Video thumbnail placeholder
        thumb = QFrame()
        thumb.setFixedSize(44, 44)
        thumb.setStyleSheet(f"""
            QFrame {{
                background-color: {theme.BG_INPUT};
                border: 1px solid {theme.BORDER_STRONG};
                border-radius: 6px;
            }}
        """)
        thumb_layout = QVBoxLayout(thumb)
        thumb_layout.setContentsMargins(0, 0, 0, 0)
        thumb_icon = QLabel("🎬")
        thumb_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_icon.setStyleSheet("font-size: 16px; background: transparent;")
        thumb_layout.addWidget(thumb_icon)
        layout.addWidget(thumb)

        # Info column
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(3)

        manifest = item.get("manifest") or {}
        title = manifest.get("title") or item.get("file_name") or "Untitled Video"
        title_lbl = QLabel(title)
        title_lbl.setWordWrap(True)
        title_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; font-weight: 600; font-size: 12px; background: transparent;")
        info_col.addWidget(title_lbl)

        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        time_str = _fmt_time(item.get("received_at", ""))
        sub_lbl = QLabel(f"{time_str} • {item.get('file_name', '')}")
        sub_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px; background: transparent;")
        sub_row.addWidget(sub_lbl)
        sub_row.addStretch(1)
        info_col.addLayout(sub_row)

        layout.addLayout(info_col, 1)

        # Target platforms mini indicators
        targets = item.get("targets") or {}
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(4)
        for p in PLATFORMS:
            t = targets.get(p)
            if t and t.get("enabled"):
                dot = QLabel("●")
                pcolor = theme.PLATFORM_COLORS.get(p, {}).get("color", theme.TEXT_MUTED)
                dot.setStyleSheet(f"color: {pcolor}; font-size: 8px; background: transparent;")
                chips_layout.addWidget(dot)
        layout.addLayout(chips_layout)


class _TargetCard(CardAlt):
    """Modern per-platform card with status badge, progress, error, and controls."""

    def __init__(self, platform: str, on_post, on_schedule, on_skip, on_toggle,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.platform = platform
        self.on_post = on_post
        self.on_schedule = on_schedule
        self.on_skip = on_skip
        self.on_toggle = on_toggle
        self.setStyleSheet(f"""
            _TargetCard {{
                background-color: {theme.BG_SURFACE_ALT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Top row: Platform chip + Checkbox + Status badge
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.enabled_cb = QCheckBox()
        self.enabled_cb.toggled.connect(self._enabled_toggled)
        top_row.addWidget(self.enabled_cb)

        self.platform_chip = PlatformChip(platform)
        top_row.addWidget(self.platform_chip)

        self.status_badge = Badge("Pending", status="pending")
        top_row.addWidget(self.status_badge)

        top_row.addStretch(1)

        # Action Buttons
        self.post_btn = PrimaryButton("Post Now")
        self.post_btn.setStyleSheet(f"""
            QPushButton#primaryBtn {{
                background-color: {theme.STATUS_SUCCESS};
                border-color: {theme.STATUS_SUCCESS};
                padding: 5px 12px;
                font-size: 12px;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: #059669;
            }}
        """)
        self.post_btn.clicked.connect(lambda: self.on_post(self.platform))

        self.skip_btn = GhostButton("Skip")
        self.skip_btn.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        self.skip_btn.clicked.connect(lambda: self.on_skip(self.platform))

        top_row.addWidget(self.post_btn)
        top_row.addWidget(self.skip_btn)
        layout.addLayout(top_row)

        # Schedule Row & Error Row
        mid_row = QHBoxLayout()
        mid_row.setSpacing(8)

        sched_label = QLabel("Schedule:")
        sched_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; font-size: 11px; font-weight: 500;")
        mid_row.addWidget(sched_label)

        self.datetime_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.datetime_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.datetime_edit.setCalendarPopup(True)
        self.datetime_edit.setFixedWidth(150)
        self.datetime_edit.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        mid_row.addWidget(self.datetime_edit)

        self.sched_btn = SecondaryButton("Set Schedule")
        self.sched_btn.setStyleSheet("padding: 5px 12px; font-size: 12px;")
        self.sched_btn.clicked.connect(lambda: self.on_schedule(self.platform, self.datetime_edit.dateTime()))
        mid_row.addWidget(self.sched_btn)

        mid_row.addStretch(1)

        # Failure / status notice
        self.notice_label = QLabel("")
        self.notice_label.setWordWrap(True)
        self.notice_label.setStyleSheet(f"color: {theme.STATUS_DANGER}; font-size: 11px;")
        mid_row.addWidget(self.notice_label, 2)
        layout.addLayout(mid_row)

        # Progress bar (for uploading state)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {theme.BG_INPUT};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.STATUS_WARNING};
                border-radius: 2px;
            }}
        """)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def _enabled_toggled(self, checked: bool) -> None:
        self.on_toggle(self.platform, checked)

    def refresh(self, tgt: dict) -> None:
        self.enabled_cb.blockSignals(True)
        self.enabled_cb.setChecked(bool(tgt.get("enabled", True)))
        self.enabled_cb.blockSignals(False)

        status = (tgt.get("status") or "pending").lower()
        self.status_badge.set_status(status, status.capitalize())

        # Progress bar visibility
        self.progress_bar.setVisible(status == "uploading")

        err = tgt.get("error") or ""
        at = tgt.get("scheduled_at")

        if status == "failed" and err:
            self.notice_label.setText(f"⚠ {err}")
            self.notice_label.setStyleSheet(f"color: {theme.STATUS_DANGER}; font-size: 11px; font-weight: 500;")
            self.notice_label.setVisible(True)
        elif status == "scheduled" and at:
            self.notice_label.setText(f"📅 Due: {at}")
            self.notice_label.setStyleSheet(f"color: {theme.STATUS_INFO}; font-size: 11px;")
            self.notice_label.setVisible(True)
        else:
            self.notice_label.setText("")
            self.notice_label.setVisible(False)


class QueueTab(QWidget):
    """Left: video list cards. Right: manifest details & platform actions."""

    def __init__(self, scheduler, queue_store, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scheduler = scheduler
        self.queue = queue_store
        self._current_item: dict | None = None
        self._rows: dict[str, _TargetCard] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 12, 16, 12)
        root_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --------------------------------------------- Left: Queue List
        left_card = Card()
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(10)

        list_header = QHBoxLayout()
        list_title = QLabel("Video Queue")
        list_title.setObjectName("sectionTitle")
        self.count_badge = Badge("0 Items", status="neutral")
        list_header.addWidget(list_title)
        list_header.addWidget(self.count_badge)
        list_header.addStretch(1)
        left_layout.addLayout(list_header)

        self.list_widget = QListWidget()
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.currentItemChanged.connect(self._selection_changed)
        left_layout.addWidget(self.list_widget, 1)

        left_card.setMinimumWidth(260)
        splitter.addWidget(left_card)

        # -------------------------------------------- Right: Item Detail
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Detail Header & Manifest Card
        self.detail_card = Card()
        detail_layout = QVBoxLayout(self.detail_card)
        detail_layout.setContentsMargins(16, 12, 16, 12)
        detail_layout.setSpacing(8)

        # Title & Meta Bar
        self.title_label = QLabel("No video selected")
        self.title_label.setObjectName("cardHeader")
        self.title_label.setWordWrap(True)
        detail_layout.addWidget(self.title_label)

        meta_row = QHBoxLayout()
        self.file_badge = QLabel("")
        self.file_badge.setStyleSheet(f"""
            color: {theme.TEXT_SECONDARY};
            background-color: {theme.BG_INPUT};
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
        """)
        meta_row.addWidget(self.file_badge)
        meta_row.addStretch(1)

        self.copy_btn = GhostButton("📋 Copy Caption")
        self.copy_btn.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.copy_btn.clicked.connect(self._copy_caption)
        meta_row.addWidget(self.copy_btn)
        detail_layout.addLayout(meta_row)

        # Caption Box
        self.caption_box = QLabel("Select a video from the queue to view its caption and configure distribution.")
        self.caption_box.setWordWrap(True)
        self.caption_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption_box.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.BG_INPUT};
                border: 1px solid {theme.BORDER_SUBTLE};
                border-radius: 6px;
                padding: 8px 12px;
                color: {theme.TEXT_PRIMARY};
                font-size: 12px;
                line-height: 1.4;
            }}
        """)
        detail_layout.addWidget(self.caption_box)

        # Hashtags row
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(6)
        self.tags_container = QWidget()
        self.tags_container.setLayout(self.tags_layout)
        detail_layout.addWidget(self.tags_container)

        right_layout.addWidget(self.detail_card)

        # Target Platforms Matrix in a Scroll Area
        targets_scroll = QScrollArea()
        targets_scroll.setWidgetResizable(True)
        targets_scroll.setFrameShape(QFrame.Shape.NoFrame)

        targets_inner = QWidget()
        targets_layout = QVBoxLayout(targets_inner)
        targets_layout.setContentsMargins(0, 0, 0, 0)
        targets_layout.setSpacing(8)

        targets_title = QLabel("Platform Distribution")
        targets_title.setObjectName("sectionTitle")
        targets_layout.addWidget(targets_title)

        for platform in PLATFORMS:
            card = _TargetCard(
                platform,
                self._post_now,
                self._schedule,
                self._skip,
                self._toggle_enabled,
                parent=targets_inner,
            )
            self._rows[platform] = card
            targets_layout.addWidget(card)

        targets_layout.addStretch(1)
        targets_scroll.setWidget(targets_inner)
        right_layout.addWidget(targets_scroll, 1)

        splitter.addWidget(right_container)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([340, 860])
        root_layout.addWidget(splitter)

        scheduler.item_updated.connect(self.refresh)
        self.refresh()

    # ------------------------------------------------------------- actions
    def _post_now(self, platform: str) -> None:
        if self._current_item:
            self.scheduler.post_now(self._current_item["id"], platform)

    def _schedule(self, platform: str, qdt: QDateTime) -> None:
        if self._current_item:
            self.scheduler.schedule(self._current_item["id"], platform, qdt)

    def _skip(self, platform: str) -> None:
        if self._current_item:
            self.scheduler.skip(self._current_item["id"], platform)

    def _toggle_enabled(self, platform: str, checked: bool) -> None:
        if self._current_item:
            tgt = self._current_item["targets"].get(platform)
            if tgt is not None:
                tgt["enabled"] = checked

    def _copy_caption(self) -> None:
        if self._current_item:
            m = self._current_item.get("manifest", {}) or {}
            caption = m.get("caption") or ""
            tags = " ".join(m.get("hashtags", []))
            full = f"{caption}\n\n{tags}".strip()
            QApplication.clipboard().setText(full)
            self.copy_btn.setText("Copied ✓")
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1500, lambda: self.copy_btn.setText("📋 Copy Caption"))

    # ------------------------------------------------------------- refresh
    @Slot()
    def refresh(self) -> None:
        """Rebuild the list and detail view from the queue store."""
        items = self.queue.all()
        current_id = self._current_item["id"] if self._current_item else None

        self.count_badge.set_status("neutral", f"{len(items)} Items")

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for item in sorted(items, key=lambda i: i.get("received_at", "")):
            lw_item = QListWidgetItem()
            lw_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            item_widget = _QueueItemWidget(item)
            lw_item.setSizeHint(item_widget.sizeHint())
            self.list_widget.addItem(lw_item)
            self.list_widget.setItemWidget(lw_item, item_widget)

            if item["id"] == current_id:
                self.list_widget.setCurrentItem(lw_item)

        self.list_widget.blockSignals(False)

        # Re-resolve current item
        if current_id:
            self._current_item = self.queue.get(current_id)
        if self._current_item is None and items:
            self.list_widget.setCurrentRow(0)
            self._current_item = items[0]
        self._refresh_detail()

    def _selection_changed(self, current, _previous) -> None:
        if current is None:
            self._current_item = None
        else:
            self._current_item = self.queue.get(current.data(Qt.ItemDataRole.UserRole))
        self._refresh_detail()

    def _refresh_detail(self) -> None:
        item = self._current_item

        # Clear existing hashtag widgets
        while self.tags_layout.count():
            w = self.tags_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        if not item:
            self.title_label.setText("No video selected")
            self.file_badge.setText("")
            self.caption_box.setText("Select a video from the queue to view its caption and configure distribution.")
            for row in self._rows.values():
                row.refresh({"enabled": False, "status": "-", "error": ""})
            return

        m = item.get("manifest", {}) or {}
        self.title_label.setText(m.get("title") or item.get("file_name", "Untitled"))
        time_str = _fmt_time(item.get("received_at", ""))
        self.file_badge.setText(f"📁 {item.get('file_name', '')}  •  Received {time_str}")
        self.caption_box.setText(m.get("caption") or "(No caption provided)")

        # Render hashtags
        hashtags = m.get("hashtags", [])
        if hashtags:
            for tag in hashtags:
                pill = QLabel(tag if tag.startswith("#") else f"#{tag}")
                pill.setStyleSheet(f"""
                    QLabel {{
                        color: {theme.ACCENT_PRIMARY};
                        background-color: {theme.BG_INPUT};
                        border: 1px solid {theme.BORDER_STRONG};
                        border-radius: 4px;
                        padding: 2px 7px;
                        font-size: 11px;
                        font-weight: 500;
                    }}
                """)
                self.tags_layout.addWidget(pill)
        self.tags_layout.addStretch(1)

        # Refresh platform target cards
        targets = item.get("targets") or {}
        for platform, row in self._rows.items():
            row.refresh(targets.get(platform, {}))

    @Slot(dict)
    def on_new_item(self, item: dict) -> None:
        """Slot for TelegramPoller.new_item: add to store, select it."""
        self.queue.add_item(item)
        self.refresh()
        for i in range(self.list_widget.count()):
            lw = self.list_widget.item(i)
            if lw.data(Qt.ItemDataRole.UserRole) == item["id"]:
                self.list_widget.setCurrentItem(lw)
                break
