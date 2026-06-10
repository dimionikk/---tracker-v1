#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI планувальника — денна шкала часу з подіями та підсвіткою конфліктів.
"""

from datetime import date, datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QDialog, QLineEdit, QTimeEdit, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QColor, QPainter

from styles import STYLE
from tools.common import section_label, icon_btn
from .manager import PlannerManager, time_to_minutes, minutes_to_time

# ──────────────────────────── КОНСТАНТИ ШКАЛИ ────────────────────────────

PX_PER_HOUR = 60
TIMELINE_HEIGHT = 24 * PX_PER_HOUR
LABEL_WIDTH = 46
TOP_PAD = 6

_WEEKDAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня",
           "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]


def format_date_ua(d: date) -> str:
    base = f"{_WEEKDAYS[d.weekday()]}, {d.day} {_MONTHS[d.month - 1]}"
    today = date.today()
    if d == today:
        return f"Сьогодні · {base}"
    if d == today - timedelta(days=1):
        return f"Вчора · {base}"
    if d == today + timedelta(days=1):
        return f"Завтра · {base}"
    return base


# ──────────────────────────── БЛОК ПОДІЇ ────────────────────────────

class EventBlock(QFrame):
    """Блок події на шкалі часу. Клік відкриває редагування."""

    def __init__(self, event: dict, conflict: bool, on_click, parent=None):
        super().__init__(parent)
        self.event_id = event["id"]
        self._on_click = on_click
        self.setObjectName("conflictBlock" if conflict else "eventBlock")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(0)

        title = QLabel(event["title"] or "Без назви")
        title.setStyleSheet("font-weight: 600; font-size: 12px; background: transparent; color: #FFFFFF;")
        lay.addWidget(title)

        end_min = time_to_minutes(event["time"]) + event["duration"]
        sub_text = f'{event["time"]}–{minutes_to_time(end_min)}'
        if conflict:
            sub_text += "  🔴 конфлікт"
        sub = QLabel(sub_text)
        sub.setStyleSheet("font-size: 10px; background: transparent; color: rgba(255,255,255,0.8);")
        lay.addWidget(sub)
        lay.addStretch()

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click(self.event_id)
        super().mousePressEvent(event)


# ──────────────────────────── ШКАЛА ЧАСУ ────────────────────────────

class TimelineWidget(QWidget):
    """Вертикальна шкала доби 00:00–24:00 з блоками подій."""

    def __init__(self, on_click=None):
        super().__init__()
        self._on_click = on_click
        self._blocks = []
        self._show_now = False
        self.setFixedHeight(TIMELINE_HEIGHT + TOP_PAD * 2)
        self.setMinimumWidth(220)

    def set_events(self, events: list, conflicts: set, show_now: bool = False):
        for b in self._blocks:
            b.deleteLater()
        self._blocks = []
        self._show_now = show_now

        for e in events:
            block = EventBlock(e, e["id"] in conflicts, self._on_click, self)
            start = time_to_minutes(e["time"])
            y = TOP_PAD + start * PX_PER_HOUR // 60
            h = max(e["duration"] * PX_PER_HOUR // 60, 18)
            block.setGeometry(LABEL_WIDTH + 6, y, self._block_width(), h)
            block.show()
            self._blocks.append(block)
        self.update()

    def _block_width(self) -> int:
        return max(self.width() - LABEL_WIDTH - 14, 40)

    def resizeEvent(self, event):
        w = self._block_width()
        for b in self._blocks:
            geo = b.geometry()
            b.setGeometry(LABEL_WIDTH + 6, geo.y(), w, geo.height())
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        for h in range(25):
            y = TOP_PAD + h * PX_PER_HOUR
            p.setPen(QColor("#3A3A3C"))
            p.drawLine(LABEL_WIDTH, y, self.width(), y)
            if h < 24:
                p.setPen(QColor("#8E8E93"))
                p.drawText(2, y + 12, f"{h:02d}:00")

        if self._show_now:
            now = datetime.now()
            y = TOP_PAD + (now.hour * 60 + now.minute) * PX_PER_HOUR // 60
            p.setPen(QColor("#FF453A"))
            p.drawLine(LABEL_WIDTH, y, self.width(), y)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FF453A"))
            p.drawEllipse(LABEL_WIDTH - 3, y - 3, 6, 6)

        p.end()


# ──────────────────────────── ДІАЛОГ ПОДІЇ ────────────────────────────

class EventDialog(QDialog):
    """Діалог створення/редагування події."""

    def __init__(self, parent=None, event: dict = None):
        super().__init__(parent)
        self.setStyleSheet(STYLE)
        self.setWindowTitle("Редагувати подію" if event else "Нова подія")
        self.setMinimumWidth(300)
        self._delete_requested = False

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        lay.addWidget(section_label("НАЗВА"))
        self.title_input = QLineEdit(event["title"] if event else "")
        self.title_input.setPlaceholderText("Напр. Зустріч з командою")
        lay.addWidget(self.title_input)

        row = QHBoxLayout()
        col1 = QVBoxLayout()
        col1.addWidget(section_label("ПОЧАТОК"))
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        if event:
            h, m = map(int, event["time"].split(":"))
            self.time_edit.setTime(QTime(h, m))
        else:
            now = QTime.currentTime()
            self.time_edit.setTime(QTime(now.hour(), (now.minute() // 5) * 5))
        col1.addWidget(self.time_edit)
        row.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(section_label("ТРИВАЛІСТЬ, ХВ"))
        self.dur_input = QSpinBox()
        self.dur_input.setRange(5, 24 * 60)
        self.dur_input.setSingleStep(5)
        self.dur_input.setValue(event["duration"] if event else 30)
        col2.addWidget(self.dur_input)
        row.addLayout(col2)
        lay.addLayout(row)

        btn_row = QHBoxLayout()
        if event:
            del_btn = QPushButton("Видалити")
            del_btn.setObjectName("stopBtn")
            del_btn.clicked.connect(self._on_delete)
            btn_row.addWidget(del_btn)
        btn_row.addStretch()
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Зберегти")
        save_btn.setObjectName("accentBtn")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        lay.addLayout(btn_row)

        self.title_input.setFocus()

    def _on_delete(self):
        self._delete_requested = True
        self.accept()

    def is_delete(self) -> bool:
        return self._delete_requested

    def get_data(self) -> dict:
        t = self.time_edit.time()
        return {
            "title": self.title_input.text().strip() or "Без назви",
            "time": f"{t.hour():02d}:{t.minute():02d}",
            "duration": self.dur_input.value(),
        }


# ──────────────────────────── ЕКРАН ПЛАНУВАЛЬНИКА ────────────────────────────

class PlannerScreen(QWidget):
    def __init__(self, pm: PlannerManager):
        super().__init__()
        self.pm = pm
        self.current_date = date.today()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(icon_btn("◀", self._shift_day, -1))
        self._date_lbl = QLabel()
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_lbl.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 600;")
        header.addWidget(self._date_lbl, 1)
        header.addWidget(icon_btn("▶", self._shift_day, 1))
        lay.addLayout(header)

        action_row = QHBoxLayout()
        today_btn = QPushButton("Сьогодні")
        today_btn.clicked.connect(self._goto_today)
        action_row.addWidget(today_btn)
        action_row.addStretch()
        add_btn = QPushButton("+ Подія")
        add_btn.setObjectName("accentBtn")
        add_btn.clicked.connect(self._add_event)
        action_row.addWidget(add_btn)
        lay.addLayout(action_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._timeline = TimelineWidget(on_click=self._edit_event)
        self._scroll.setWidget(self._timeline)
        lay.addWidget(self._scroll, 1)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(60_000)

    def refresh(self):
        self._date_lbl.setText(format_date_ua(self.current_date))
        events = self.pm.events_for_date(self.current_date.isoformat())
        conflicts = PlannerManager.find_conflicts(events)
        is_today = self.current_date == date.today()
        self._timeline.set_events(events, conflicts, is_today)

        target = (datetime.now().hour - 1) * PX_PER_HOUR if is_today else 7 * PX_PER_HOUR
        self._scroll.verticalScrollBar().setValue(max(0, target))

    def _tick(self):
        if self.current_date == date.today():
            self._timeline.update()

    def _shift_day(self, delta: int):
        self.current_date += timedelta(days=delta)
        self.refresh()

    def _goto_today(self):
        self.current_date = date.today()
        self.refresh()

    def _add_event(self):
        dlg = EventDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self.pm.add_event(self.current_date.isoformat(), data["time"], data["duration"], data["title"])
            self.refresh()

    def _edit_event(self, event_id: str):
        event = self.pm.get_event(event_id)
        if not event:
            return
        dlg = EventDialog(self, event)
        if dlg.exec():
            if dlg.is_delete():
                self.pm.delete_event(event_id)
            else:
                self.pm.update_event(event_id, **dlg.get_data())
            self.refresh()
