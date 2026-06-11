import calendar
from datetime import date, datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QScrollArea,
    QFrame, QDialog, QLineEdit, QTimeEdit, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QTime
from PyQt6.QtGui import QColor, QPainter

from styles import STYLE
from tools.common import section_label, icon_btn, format_date_ua, clear_layout
from tools.logger import log
from tools.settings.screen import SettingsScreen
from .manager import PlannerManager, time_to_minutes, minutes_to_time

PX_PER_HOUR = 46
TIMELINE_HEIGHT = 24 * PX_PER_HOUR
LABEL_WIDTH = 38
TOP_PAD = 4
DAY_START_HOUR = 7

def _shift_minutes(minutes: int) -> int:
    """Convert real time-of-day minutes to position-minutes where DAY_START_HOUR is 0."""
    return (minutes - DAY_START_HOUR * 60) % (24 * 60)

def _unshift_minutes(pos_minutes: int) -> int:
    """Convert position-minutes (0 = DAY_START_HOUR) back to real time-of-day minutes."""
    return (pos_minutes + DAY_START_HOUR * 60) % (24 * 60)

class EventBlock(QFrame):

    def __init__(self, event: dict, conflict: bool, on_click, parent=None):
        super().__init__(parent)
        self.event_id = event["id"]
        self._on_click = on_click
        self.setObjectName("conflictBlock" if conflict else "eventBlock")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 1, 6, 1)
        lay.setSpacing(0)

        title = QLabel(event["title"] or "Без назви")
        title.setStyleSheet("font-weight: 600; font-size: 11px; background: transparent; color: #FFFFFF;")
        lay.addWidget(title)

        end_min = time_to_minutes(event["time"]) + event["duration"]
        sub_text = f'{event["time"]}–{minutes_to_time(end_min)}'
        if conflict:
            sub_text += "  🔴 конфлікт"
        sub = QLabel(sub_text)
        sub.setStyleSheet("font-size: 9px; background: transparent; color: rgba(255,255,255,0.8);")
        lay.addWidget(sub)
        lay.addStretch()

    def mousePressEvent(self, event):
        if self._on_click:
            event_id = self.event_id
            on_click = self._on_click
            QTimer.singleShot(0, lambda: on_click(event_id))
        super().mousePressEvent(event)

class TimelineWidget(QWidget):

    def __init__(self, on_click=None, on_double_click=None):
        super().__init__()
        self._on_click = on_click
        self._on_double_click = on_double_click
        self._blocks = []
        self._show_now = False
        self.setFixedHeight(TIMELINE_HEIGHT + TOP_PAD * 2)
        self.setMinimumWidth(200)

    def set_events(self, events: list, conflicts: set, show_now: bool = False):
        for b in self._blocks:
            b.deleteLater()
        self._blocks = []
        self._show_now = show_now

        for e in events:
            block = EventBlock(e, e["id"] in conflicts, self._on_click, self)
            start = _shift_minutes(time_to_minutes(e["time"]))
            y = TOP_PAD + start * PX_PER_HOUR // 60
            h = max(e["duration"] * PX_PER_HOUR // 60, 16)
            block.setGeometry(LABEL_WIDTH + 4, y, self._block_width(), h)
            block.show()
            self._blocks.append(block)
        self.update()

    def _block_width(self) -> int:
        return max(self.width() - LABEL_WIDTH - 10, 36)

    def mouseDoubleClickEvent(self, event):
        if self._on_double_click:
            y = event.position().y()
            minutes = int((y - TOP_PAD) * 60 // PX_PER_HOUR)
            minutes = max(0, min(minutes, 24 * 60 - 5))
            minutes = (minutes // 5) * 5
            self._on_double_click(_unshift_minutes(minutes))
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        w = self._block_width()
        for b in self._blocks:
            geo = b.geometry()
            b.setGeometry(LABEL_WIDTH + 4, geo.y(), w, geo.height())
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)

        for h in range(25):
            y = TOP_PAD + h * PX_PER_HOUR
            p.setPen(QColor("#3A3A3C"))
            p.drawLine(LABEL_WIDTH, y, self.width(), y)
            if h < 24:
                p.setPen(QColor("#8E8E93"))
                real_hour = (DAY_START_HOUR + h) % 24
                p.drawText(2, y + 11, f"{real_hour:02d}:00")

        if self._show_now:
            now = datetime.now()
            pos_minutes = _shift_minutes(now.hour * 60 + now.minute)
            y = TOP_PAD + pos_minutes * PX_PER_HOUR // 60
            p.setPen(QColor("#FF453A"))
            p.drawLine(LABEL_WIDTH, y, self.width(), y)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#FF453A"))
            p.drawEllipse(LABEL_WIDTH - 3, y - 3, 6, 6)

        p.end()

class EventDialog(QDialog):

    def __init__(self, parent=None, event: dict = None, initial_time: str = None):
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
        elif initial_time:
            h, m = map(int, initial_time.split(":"))
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

_WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
_MONTH_NAMES = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
                "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]

class MiniDayCell(QFrame):
    def __init__(self, day: date, count: int, is_today: bool, is_selected: bool, on_click):
        super().__init__()
        self._day = day
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(29, 29)

        if is_selected:
            bg, border, fg = "#7B6CF6", "#7B6CF6", "#FFFFFF"
        elif is_today:
            bg, border, fg = "#2C2C2E", "#7B6CF6", "#FFFFFF"
        else:
            bg, border, fg = "#2C2C2E", "transparent", "#FFFFFF"

        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 6px; border: 1px solid {border}; }}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 1)
        lay.setSpacing(0)

        num = QLabel(str(day.day))
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"color: {fg}; font-size: 12px; font-weight: 600; border: none; background: transparent;")
        lay.addWidget(num)

        if count > 0:
            badge_bg = "#FFFFFF" if is_selected else "#7B6CF6"
            badge_fg = "#7B6CF6" if is_selected else "#FFFFFF"
            badge = QLabel(str(count) if count < 10 else "9+")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedSize(14, 14)
            badge.setStyleSheet(
                f"color: {badge_fg}; background: {badge_bg}; font-size: 9px; font-weight: 700; "
                f"border-radius: 7px; border: none;"
            )
            badge_row = QHBoxLayout()
            badge_row.setContentsMargins(0, 0, 0, 0)
            badge_row.addStretch()
            badge_row.addWidget(badge)
            badge_row.addStretch()
            lay.addLayout(badge_row)
        else:
            spacer = QLabel("")
            spacer.setFixedHeight(14)
            spacer.setStyleSheet("border: none; background: transparent;")
            lay.addWidget(spacer)

    def mousePressEvent(self, event):
        if self._on_click:
            day = self._day
            on_click = self._on_click
            QTimer.singleShot(0, lambda: on_click(day))
        super().mousePressEvent(event)

class MonthCalendar(QFrame):
    def __init__(self, year: int, month: int, event_counts: dict, selected: date, on_day_click):
        super().__init__()
        self.setStyleSheet("QFrame { background: transparent; }")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        title = QLabel(f"{_MONTH_NAMES[month - 1]} {year}")
        title.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600; border: none;")
        lay.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)
        for col, wd in enumerate(_WEEKDAY_SHORT):
            lbl = QLabel(wd)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #8E8E93; font-size: 10px; border: none;")
            grid.addWidget(lbl, 0, col)

        first = date(year, month, 1)
        days_in_month = calendar.monthrange(year, month)[1]
        today = date.today()
        row, col = 1, first.weekday()
        for day_num in range(1, days_in_month + 1):
            d = date(year, month, day_num)
            cell = MiniDayCell(d, event_counts.get(day_num, 0), d == today, d == selected, on_day_click)
            grid.addWidget(cell, row, col)
            col += 1
            if col > 6:
                col = 0
                row += 1

        # Keep the grid compact (no stretching gaps between day cells); push
        # any leftover horizontal space to the right of the calendar instead.
        grid_row = QHBoxLayout()
        grid_row.setContentsMargins(0, 0, 0, 0)
        grid_row.addLayout(grid)
        grid_row.addStretch()
        lay.addLayout(grid_row)

class PlannerScreen(QWidget):
    def __init__(self, pm: PlannerManager, sm=None):
        super().__init__()
        self.pm = pm
        self.sm = sm
        self.current_date = date.today()
        self._year = date.today().year
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)

        # --- Left: detailed plan for the selected day ---
        self._day_view = QWidget()
        dv = QVBoxLayout(self._day_view)
        dv.setContentsMargins(0, 0, 0, 0)
        dv.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(icon_btn("◀", self._shift_day, -1))
        self._date_lbl = QLabel()
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._date_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600;")
        header.addWidget(self._date_lbl, 1)
        header.addWidget(icon_btn("▶", self._shift_day, 1))
        dv.addLayout(header)

        action_row = QHBoxLayout()
        today_btn = QPushButton("Сьогодні")
        today_btn.setFixedHeight(28)
        today_btn.clicked.connect(self._goto_today)
        action_row.addWidget(today_btn)
        action_row.addStretch()
        notif_btn = QPushButton("🔔 Сповіщення")
        notif_btn.setFixedHeight(28)
        notif_btn.clicked.connect(self._open_notifications)
        action_row.addWidget(notif_btn)
        add_btn = QPushButton("+ Подія")
        add_btn.setObjectName("accentBtn")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._add_event)
        action_row.addWidget(add_btn)
        dv.addLayout(action_row)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._timeline = TimelineWidget(on_click=self._edit_event, on_double_click=self._add_event_at_time)
        self._scroll.setWidget(self._timeline)
        dv.addWidget(self._scroll, 1)

        lay.addWidget(self._day_view, 5)

        # --- Right: year overview ---
        self._year_view = QWidget()
        yv = QVBoxLayout(self._year_view)
        yv.setContentsMargins(0, 0, 0, 0)
        yv.setSpacing(6)

        year_header = QHBoxLayout()
        year_header.addWidget(icon_btn("◀", self._shift_year, -1))
        self._year_lbl = QLabel()
        self._year_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._year_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600;")
        year_header.addWidget(self._year_lbl, 1)
        year_header.addWidget(icon_btn("▶", self._shift_year, 1))
        yv.addLayout(year_header)

        self._year_scroll = QScrollArea()
        self._year_scroll.setWidgetResizable(True)
        self._year_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._year_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._year_content = QWidget()
        self._year_layout = QVBoxLayout(self._year_content)
        self._year_layout.setContentsMargins(0, 0, 0, 0)
        self._year_layout.setSpacing(8)
        self._year_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._year_scroll.setWidget(self._year_content)
        yv.addWidget(self._year_scroll, 1)

        lay.addWidget(self._year_view, 2)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(60_000)

    def refresh(self):
        self._date_lbl.setText(format_date_ua(self.current_date))
        events = self.pm.events_for_date(self.current_date.isoformat())
        conflicts = PlannerManager.find_conflicts(events)
        is_today = self.current_date == date.today()
        self._timeline.set_events(events, conflicts, is_today)

        if is_today:
            now = datetime.now()
            pos_minutes = _shift_minutes(now.hour * 60 + now.minute)
            target = (pos_minutes // 60 - 1) * PX_PER_HOUR
        else:
            target = 0
        self._scroll.verticalScrollBar().setValue(max(0, target))

        self._refresh_year_view()

    def _refresh_year_view(self):
        clear_layout(self._year_layout)
        self._year_lbl.setText(str(self._year))
        for month in range(1, 13):
            event_counts = self._event_counts_for_month(self._year, month)
            cal = MonthCalendar(self._year, month, event_counts, self.current_date, self._select_day)
            self._year_layout.addWidget(cal)

    def _event_counts_for_month(self, year: int, month: int) -> dict:
        prefix = f"{year:04d}-{month:02d}-"
        counts = {}
        for e in self.pm.data["events"]:
            if e["date"].startswith(prefix):
                d = int(e["date"][8:10])
                counts[d] = counts.get(d, 0) + 1
        return counts

    def _select_day(self, day: date):
        self.current_date = day
        self._year = day.year
        self.refresh()

    def _shift_year(self, delta: int):
        self._year += delta
        self._refresh_year_view()

    def _tick(self):
        if self.current_date == date.today():
            self._timeline.update()

    def _shift_day(self, delta: int):
        self.current_date += timedelta(days=delta)
        if self.current_date.year != self._year:
            self._year = self.current_date.year
        self.refresh()

    def _goto_today(self):
        self.current_date = date.today()
        self._year = self.current_date.year
        self.refresh()

    def _add_event(self):
        dlg = EventDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            self.pm.add_event(self.current_date.isoformat(), data["time"], data["duration"], data["title"])
            self.refresh()

    def _add_event_at_time(self, minutes: int):
        dlg = EventDialog(self, initial_time=minutes_to_time(minutes))
        if dlg.exec():
            data = dlg.get_data()
            self.pm.add_event(self.current_date.isoformat(), data["time"], data["duration"], data["title"])
            self.refresh()

    def _open_notifications(self):
        dlg = QDialog(self)
        dlg.setStyleSheet(STYLE)
        dlg.setWindowTitle("Сповіщення")
        dlg.setMinimumSize(420, 580)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(SettingsScreen(self.sm))
        log("PLANNER", "Відкрито налаштування сповіщень")
        dlg.exec()

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
