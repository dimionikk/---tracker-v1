#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Трекер активності — PyQt6
Залежності: pip install PyQt6 psutil
Windows додатково: pip install pywin32
Linux додатково: sudo apt install xdotool
"""

import sys
import json
import os
import uuid
import time
import subprocess
from datetime import datetime, timedelta, date
from pathlib import Path

import psutil
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QComboBox, QScrollArea, QFrame,
    QStackedWidget, QSystemTrayIcon, QMenu, QCheckBox, QLineEdit,
    QDialog, QListWidget, QMessageBox, QColorDialog
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter

# ──────────────────────────── CONSTANTS ────────────────────────────

DATA_FILE = Path(os.path.dirname(os.path.abspath(__file__))) / "tracker_data.json"

CATEGORY_COLORS = [
    '#7B6CF6', '#4CAF50', '#2196F3', '#FF9800',
    '#FF453A', '#00BCD4', '#E91E63', '#9C27B0'
]

STYLE = """
QWidget {
    background-color: #1C1C1E;
    color: #FFFFFF;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #2C2C2E; width: 5px; border-radius: 2px;
}
QScrollBar::handle:vertical { background: #48484A; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QPushButton {
    background-color: #3A3A3C; color: #FFFFFF;
    border: none; border-radius: 10px; padding: 8px 16px;
}
QPushButton:hover { background-color: #48484A; }
QPushButton:pressed { background-color: #636366; }
QPushButton#accentBtn { background-color: #7B6CF6; }
QPushButton#accentBtn:hover { background-color: #8E7FF8; }
QPushButton#stopBtn {
    background-color: #2C1C1C; color: #FF453A;
    border: 1px solid #FF453A; border-radius: 10px;
}
QPushButton#stopBtn:hover { background-color: #FF453A; color: #FFFFFF; }

QComboBox {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C; border-radius: 10px; padding: 8px 12px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C;
    selection-background-color: #3A3A3C;
}
QLineEdit {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C; border-radius: 8px; padding: 6px 10px;
}
QLineEdit:focus { border-color: #7B6CF6; }
QLabel { background: transparent; }

QCheckBox::indicator {
    width: 40px; height: 24px; border-radius: 12px;
    background-color: #3A3A3C;
}
QCheckBox::indicator:checked { background-color: #7B6CF6; }

QListWidget {
    background: #2C2C2E; border-radius: 8px;
    border: 1px solid #3A3A3C;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #3A3A3C; }

QDialog { background: #1C1C1E; }
QMenu {
    background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px;
}
QMenu::item { padding: 8px 16px; }
QMenu::item:selected { background: #3A3A3C; }
"""

# ──────────────────────────── HELPERS ────────────────────────────

def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h}г {m:02d}хв"

def fmt_timer(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# ──────────────────────────── DATA MANAGER ────────────────────────────

class DataManager:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default()

    def save(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)

    def _default(self) -> dict:
        return {
            "categories": [
                {"id": "study",   "name": "Навчання", "color": "#7B6CF6"},
                {"id": "games",   "name": "Ігри",      "color": "#4CAF50"},
                {"id": "work",    "name": "Робота",    "color": "#2196F3"},
                {"id": "leisure", "name": "Дозвілля",  "color": "#FF9800"},
            ],
            "app_mappings": [],
            "sessions": [],
            "settings": {"autostart": False, "reminders": False},
            "active_session": None,
        }

    # ── Shortcuts ──
    @property
    def categories(self) -> list:
        return self.data["categories"]

    @property
    def sessions(self) -> list:
        return self.data["sessions"]

    @property
    def app_mappings(self) -> list:
        return self.data["app_mappings"]

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def active_session(self) -> dict | None:
        return self.data.get("active_session")

    # ── Category helpers ──
    def get_category(self, cat_id: str) -> dict | None:
        return next((c for c in self.categories if c["id"] == cat_id), None)

    def add_category(self, name: str, color: str):
        self.categories.append({"id": str(uuid.uuid4()), "name": name, "color": color})
        self.save()

    def remove_category(self, cat_id: str):
        self.data["categories"] = [c for c in self.categories if c["id"] != cat_id]
        self.save()

    # ── App mapping helpers ──
    def get_category_for_process(self, process_name: str) -> str | None:
        pl = process_name.lower()
        for m in self.app_mappings:
            if m["process"].lower() == pl:
                return m["category_id"]
        return None

    def add_mapping(self, process: str, category_id: str):
        # Replace existing mapping for same process if any
        self.data["app_mappings"] = [m for m in self.app_mappings if m["process"].lower() != process.lower()]
        self.app_mappings.append({"process": process, "category_id": category_id})
        self.save()

    def remove_mapping(self, process: str):
        self.data["app_mappings"] = [m for m in self.app_mappings if m["process"] != process]
        self.save()

    # ── Session helpers ──
    def start_session(self, category_id: str) -> dict:
        if self.active_session:
            self._commit_active()
        session = {
            "id": str(uuid.uuid4()),
            "category_id": category_id,
            "start": datetime.now().isoformat(),
            "end": None,
            "duration": 0,
        }
        self.data["active_session"] = session
        self.save()
        return session

    def stop_session(self) -> dict | None:
        if not self.active_session:
            return None
        return self._commit_active()

    def _commit_active(self) -> dict:
        s = self.active_session
        end = datetime.now()
        start = datetime.fromisoformat(s["start"])
        s["end"] = end.isoformat()
        s["duration"] = max(1, int((end - start).total_seconds()))
        self.sessions.append(s)
        self.data["active_session"] = None
        self.save()
        return s

    # ── Stats ──
    def get_today_time(self, category_id: str) -> int:
        today = date.today().isoformat()
        total = sum(
            s["duration"] for s in self.sessions
            if s["category_id"] == category_id
            and s["start"][:10] == today
            and s.get("end")
        )
        if self.active_session and self.active_session["category_id"] == category_id:
            start = datetime.fromisoformat(self.active_session["start"])
            total += int((datetime.now() - start).total_seconds())
        return total

    def get_period_stats(self, period: str) -> dict:
        now = datetime.now()
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            cutoff = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        stats = {c["id"]: 0 for c in self.categories}
        for s in self.sessions:
            if s.get("end") and datetime.fromisoformat(s["start"]) >= cutoff:
                cid = s["category_id"]
                stats[cid] = stats.get(cid, 0) + s["duration"]
        if self.active_session:
            s = self.active_session
            if datetime.fromisoformat(s["start"]) >= cutoff:
                start = datetime.fromisoformat(s["start"])
                cid = s["category_id"]
                stats[cid] = stats.get(cid, 0) + int((datetime.now() - start).total_seconds())
        return stats

    def get_today_sessions(self) -> list:
        today = date.today().isoformat()
        result = [s for s in self.sessions if s["start"][:10] == today and s.get("end")]
        result.sort(key=lambda s: s["start"], reverse=True)
        return result

# ──────────────────────────── WINDOW TRACKER THREAD ────────────────────────────

class WindowTrackerThread(QThread):
    window_changed = pyqtSignal(str, str)   # process_name, title

    def __init__(self):
        super().__init__()
        self._running = True
        self._last_process = ""

    def _get_active(self):
        try:
            if sys.platform == "win32":
                import win32gui
                import win32process
                hwnd = win32gui.GetForegroundWindow()
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                title = win32gui.GetWindowText(hwnd)
                return psutil.Process(pid).name(), title
            else:
                pid = subprocess.check_output(
                    ["xdotool", "getactivewindow", "getwindowpid"],
                    stderr=subprocess.DEVNULL, timeout=2
                ).decode().strip()
                title = subprocess.check_output(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    stderr=subprocess.DEVNULL, timeout=2
                ).decode().strip()
                return psutil.Process(int(pid)).name(), title
        except Exception:
            return None, None

    def run(self):
        while self._running:
            proc, title = self._get_active()
            if proc and proc != self._last_process:
                self._last_process = proc
                self.window_changed.emit(proc, title or "")
            time.sleep(3)

    def stop(self):
        self._running = False

# ──────────────────────────── BAR WIDGET ────────────────────────────

class BarWidget(QWidget):
    def __init__(self, ratio: float, color: str):
        super().__init__()
        self._ratio = min(1.0, max(0.0, ratio))
        self._color = QColor(color)
        self.setFixedHeight(8)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#3A3A3C"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), 8, 4, 4)
        fw = int(self.width() * self._ratio)
        if fw > 0:
            p.setBrush(self._color)
            p.drawRoundedRect(0, 0, fw, 8, 4, 4)
        p.end()

# ──────────────────────────── CATEGORY CARD ────────────────────────────

class CategoryCard(QFrame):
    def __init__(self, category: dict, seconds: int, active: bool = False):
        super().__init__()
        self.setFixedHeight(80)
        border = category["color"] if active else "#3A3A3C"
        self.setStyleSheet(
            f"QFrame {{ background: #2C2C2E; border-radius: 12px; border: 1.5px solid {border}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {category['color']}; font-size: 10px; border: none;")
        name = QLabel(category["name"])
        name.setStyleSheet("color: #8E8E93; font-size: 11px; border: none;")
        top.addWidget(dot)
        top.addWidget(name)
        top.addStretch()
        lay.addLayout(top)

        time_lbl = QLabel(fmt_time(seconds))
        time_lbl.setStyleSheet("color: #FFFFFF; font-size: 19px; font-weight: 500; border: none;")
        lay.addWidget(time_lbl)

# ──────────────────────────── TRACKER SCREEN ────────────────────────────

class TrackerScreen(QWidget):
    def __init__(self, dm: DataManager, on_global_refresh=None):
        super().__init__()
        self.dm = dm
        self._on_global_refresh = on_global_refresh
        self._setup_ui()
        self._tick = QTimer()
        self._tick.timeout.connect(self._update_timer)
        self._tick.start(1000)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        # Tab switcher
        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(["Ручний", "Авто", "Статист.", "Налашт.", "?"]):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton { background: #2C2C2E; border-radius: 8px; }
                QPushButton:checked { background: #7B6CF6; }
            """)
            btn.clicked.connect(lambda _, idx=i: self._switch_tab(idx))
            tab_row.addWidget(btn)
            self._tab_btns.append(btn)
        tab_row.addStretch()
        self._tab_btns[0].setChecked(True)
        root.addLayout(tab_row)

        self._tab_stack = QStackedWidget()
        self._tab_stack.addWidget(self._build_manual_page())
        self._tab_stack.addWidget(self._build_auto_page())
        self._stats_page = StatisticsScreen(self.dm)
        self._tab_stack.addWidget(self._stats_page)
        self._settings_page = SettingsScreen(self.dm, self._global_refresh)
        self._tab_stack.addWidget(self._settings_page)
        self._tab_stack.addWidget(self._build_help_page())
        root.addWidget(self._tab_stack)

        self.refresh()

    def _global_refresh(self):
        self.refresh()
        self._stats_page.refresh()
        if self._on_global_refresh:
            self._on_global_refresh()

    def _switch_tab(self, idx: int):
        self._tab_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._tab_btns):
            btn.setChecked(i == idx)
        if idx == 1:
            self._refresh_auto()
        elif idx == 2:
            self._stats_page.refresh()
        elif idx == 3:
            self._settings_page.refresh()
        # idx == 4: help page, no refresh needed
        # idx == 4 (help) needs no refresh

    def _build_help_page(self) -> QWidget:
        outer = QWidget()
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 16)
        lay.setSpacing(14)

        def section(title: str, body: str):
            card = QWidget()
            card.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 12px; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            h = QLabel(title)
            h.setStyleSheet("color: #7B6CF6; font-size: 13px; font-weight: 700; background: transparent;")
            h.setWordWrap(True)
            b = QLabel(body)
            b.setStyleSheet("color: #EBEBF5; font-size: 13px; background: transparent; line-height: 1.4;")
            b.setWordWrap(True)
            cl.addWidget(h)
            cl.addWidget(b)
            lay.addWidget(card)

        section("⏱  Ручний трекер",
            "Обери категорію зі списку і натисни ▶. Натисни ⏹ Стоп коли закінчив. "
            "Всі сесії відображаються в журналі нижче.")

        section("🔄  Авто трекер",
            "Відкрий вкладку «Авто» і додай правило: назва.exe → категорія. "
            "Трекер кожні 3 секунди дивиться яке вікно активне і сам запускає або зупиняє сесію. "
            "Щоб знайти потрібний процес — натисни «Показати запущені процеси».")

        section("📊  Статистика",
            "Показує час по категоріях за сьогодні, тиждень або місяць у вигляді барів. "
            "Перемикай період кнопками зверху.")

        section("⚙  Категорії",
            "У вкладці «Налашт.» додавай, редагуй і видаляй категорії. "
            "Колір обирається при створенні. Після видалення категорії її сесії зникають зі статистики.")

        section("🖥  Трей",
            "Закриття вікна не зупиняє програму — вона лишається в системному треї. "
            "Клік по іконці → відкрити. ПКМ → Вийти щоб повністю закрити.")

        section("🔒  Один екземпляр",
            "Якщо програма вже запущена в треї — повторний запуск буде заблокований. "
            "Спочатку виходь через трей, потім запускай знову.")

        lay.addStretch()
        scroll.setWidget(inner)
        ol.addWidget(scroll)
        return outer

    def _build_help_page(self) -> QWidget:
        outer = QWidget()
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 4, 16)
        lay.setSpacing(12)

        def section(emoji_title: str, body: str):
            card = QWidget()
            card.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 12px; }")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            h = QLabel(emoji_title)
            h.setStyleSheet("color: #7B6CF6; font-size: 13px; font-weight: 700; background: transparent;")
            h.setWordWrap(True)
            b = QLabel(body)
            b.setStyleSheet("color: #EBEBF5; font-size: 12px; background: transparent;")
            b.setWordWrap(True)
            cl.addWidget(h)
            cl.addWidget(b)
            lay.addWidget(card)

        section("Ручний трекер",
            "Обери категорію зі списку і натисни > щоб почати. "
            "Натисни Stop коли закінчив. "
            "Всі сесії відображаються в журналі нижче.")

        section("Авто трекер",
            "Відкрий вкладку Авто і додай правило: назва.exe -> категорія. "
            "Трекер кожні 3 секунди дивиться яке вікно активне і сам запускає або зупиняє сесію. "
            "Щоб знайти потрібний процес — натисни Показати запущені процеси.")

        section("Статистика",
            "Показує час по категоріях за сьогодні, тиждень або місяць у вигляді барів. "
            "Перемикай період кнопками зверху.")

        section("Категорії (Налашт.)",
            "Додавай, редагуй і видаляй категорії. "
            "Колір обирається при створенні. "
            "Після видалення категорії її сесії зникають зі статистики.")

        section("Трей",
            "Закриття вікна не зупиняє програму — вона лишається в системному треї. "
            "Клік по іконці — відкрити. ПКМ -> Вийти щоб повністю зупинити.")

        section("Один екземпляр",
            "Якщо програма вже в треї — повторний запуск буде заблокований. "
            "Спочатку виходь через трей, потім запускай знову.")

        lay.addStretch()
        scroll.setWidget(inner)
        ol.addWidget(scroll)
        return outer

    def _build_manual_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)

        lbl = QLabel("СЬОГОДНІ")
        lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        lay.addWidget(lbl)

        self._cards_container = QWidget()
        self._cards_grid = QGridLayout(self._cards_container)
        self._cards_grid.setSpacing(8)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._cards_container)

        timer_frame = QFrame()
        timer_frame.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; }")
        timer_frame.setMinimumHeight(130)
        tl = QVBoxLayout(timer_frame)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setSpacing(6)

        self._timer_status = QLabel("Оберіть категорію і натисни ▶")
        self._timer_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_status.setStyleSheet("color: #8E8E93; font-size: 13px;")

        self._timer_display = QLabel("00:00:00")
        self._timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_display.setStyleSheet(
            "color: #FFFFFF; font-size: 44px; font-weight: 300; font-family: 'Courier New', monospace;"
        )

        self._stop_btn = QPushButton("⏹  Стоп")
        self._stop_btn.setObjectName("stopBtn")
        self._stop_btn.setFixedWidth(130)
        self._stop_btn.hide()
        self._stop_btn.clicked.connect(self._on_stop)

        tl.addWidget(self._timer_status)
        tl.addWidget(self._timer_display)
        stop_row = QHBoxLayout()
        stop_row.addStretch()
        stop_row.addWidget(self._stop_btn)
        stop_row.addStretch()
        tl.addLayout(stop_row)
        lay.addWidget(timer_frame)

        ctrl = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.addItem("Оберіть категорію…")
        self._start_btn = QPushButton("▶")
        self._start_btn.setObjectName("accentBtn")
        self._start_btn.setFixedSize(42, 42)
        self._start_btn.clicked.connect(self._on_start)
        ctrl.addWidget(self._combo)
        ctrl.addWidget(self._start_btn)
        lay.addLayout(ctrl)

        jlbl = QLabel("ЖУРНАЛ")
        jlbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        lay.addWidget(jlbl)

        self._journal_inner = QWidget()
        self._journal_layout = QVBoxLayout(self._journal_inner)
        self._journal_layout.setContentsMargins(0, 0, 0, 0)
        self._journal_layout.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidget(self._journal_inner)
        scroll.setWidgetResizable(True)
        lay.addWidget(scroll)

        return page

    def _build_auto_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(10)

        self._auto_status = QLabel("Автовідстеження не активне")
        self._auto_status.setStyleSheet(
            "color: #8E8E93; font-size: 12px; background: #2C2C2E; border-radius: 8px; padding: 8px 12px;"
        )
        lay.addWidget(self._auto_status)

        lay.addWidget(_section_label("ПРОГРАМИ"))
        self._auto_map_widget = QWidget()
        self._auto_map_layout = QVBoxLayout(self._auto_map_widget)
        self._auto_map_layout.setContentsMargins(0, 0, 0, 0)
        self._auto_map_layout.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidget(self._auto_map_widget)
        scroll.setWidgetResizable(True)
        lay.addWidget(scroll)

        lay.addWidget(_section_label("ДОДАТИ"))
        add_row = QHBoxLayout()
        self._auto_proc_input = QLineEdit()
        self._auto_proc_input.setPlaceholderText("Назва процесу (напр. chrome.exe)")
        self._auto_cat_combo = QComboBox()
        self._auto_cat_combo.setFixedWidth(115)
        add_btn = QPushButton("+ Додати")
        add_btn.setObjectName("accentBtn")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_auto_mapping)
        add_row.addWidget(self._auto_proc_input)
        add_row.addWidget(self._auto_cat_combo)
        add_row.addWidget(add_btn)
        lay.addLayout(add_row)

        running_btn = QPushButton("📋  Показати запущені процеси")
        running_btn.clicked.connect(self._show_running_auto)
        lay.addWidget(running_btn)

        return page

    def _refresh_auto(self):
        _clear_layout(self._auto_map_layout)
        for m in self.dm.app_mappings:
            self._auto_map_layout.addWidget(self._auto_map_row(m))
        if not self.dm.app_mappings:
            hint = QLabel("Немає програм. Додай процес → категорія.")
            hint.setStyleSheet("color: #48484A; font-size: 12px; padding: 4px;")
            self._auto_map_layout.addWidget(hint)
        self._auto_map_layout.addStretch()
        self._auto_cat_combo.clear()
        for cat in self.dm.categories:
            self._auto_cat_combo.addItem(cat["name"])
        if self.dm.active_session:
            cat = self.dm.get_category(self.dm.active_session["category_id"])
            name  = cat["name"]  if cat else "?"
            color = cat["color"] if cat else "#888"
            self._auto_status.setText(f"Зараз відстежується: {name}")
            self._auto_status.setStyleSheet(
                f"color: {color}; font-size: 12px; background: #2C2C2E; border-radius: 8px; padding: 8px 12px;"
            )
        else:
            self._auto_status.setText("Автовідстеження не активне")
            self._auto_status.setStyleSheet(
                "color: #8E8E93; font-size: 12px; background: #2C2C2E; border-radius: 8px; padding: 8px 12px;"
            )

    def _auto_map_row(self, m: dict) -> QWidget:
        cat = self.dm.get_category(m["category_id"])
        w = QWidget()
        w.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 8px; }")
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 8, 8, 8)
        proc_lbl = QLabel(m["process"])
        proc_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        arrow = QLabel("→")
        arrow.setStyleSheet("color: #8E8E93; background: transparent;")
        cat_lbl = QLabel(cat["name"] if cat else "?")
        color = cat["color"] if cat else "#888"
        cat_lbl.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
        del_btn = QPushButton("✕")
        del_btn.setFixedSize(28, 28)
        del_btn.setStyleSheet("background: #3A3A3C; border-radius: 6px; color: #FF453A;")
        del_btn.clicked.connect(lambda _, proc=m["process"]: (self.dm.remove_mapping(proc), self._refresh_auto()))
        rl.addWidget(proc_lbl)
        rl.addWidget(arrow)
        rl.addWidget(cat_lbl)
        rl.addStretch()
        rl.addWidget(del_btn)
        return w

    def _add_auto_mapping(self):
        proc = self._auto_proc_input.text().strip()
        if not proc or self._auto_cat_combo.count() == 0:
            return
        cat = self.dm.categories[self._auto_cat_combo.currentIndex()]
        self.dm.add_mapping(proc, cat["id"])
        self._auto_proc_input.clear()
        self._refresh_auto()

    def _show_running_auto(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Запущені процеси")
        dlg.setMinimumWidth(340)
        dlg.setMinimumHeight(460)
        dlg.setStyleSheet(STYLE)
        ll = QVBoxLayout(dlg)
        search = QLineEdit()
        search.setPlaceholderText("🔍  Пошук процесу…")
        ll.addWidget(search)
        lw = QListWidget()
        procs = sorted({p.name() for p in psutil.process_iter(["name"])})
        lw.addItems(procs)
        def on_search(text):
            lw.clear()
            t = text.lower()
            lw.addItems([p for p in procs if t in p.lower()])
        search.textChanged.connect(on_search)
        def pick():
            items = lw.selectedItems()
            if items:
                self._auto_proc_input.setText(items[0].text())
                dlg.accept()
        lw.itemDoubleClicked.connect(lambda _: pick())
        btn = QPushButton("Обрати")
        btn.setObjectName("accentBtn")
        btn.clicked.connect(pick)
        ll.addWidget(lw)
        ll.addWidget(btn)
        search.setFocus()
        dlg.exec()

    def refresh(self):
        # Rebuild combo
        prev_idx = self._combo.currentIndex()
        self._combo.clear()
        self._combo.addItem("Оберіть категорію…")
        for c in self.dm.categories:
            self._combo.addItem(c["name"])
        if 0 < prev_idx <= len(self.dm.categories):
            self._combo.setCurrentIndex(prev_idx)

        # Rebuild cards
        _clear_layout(self._cards_grid)
        active_cid = self.dm.active_session["category_id"] if self.dm.active_session else None
        for i, cat in enumerate(self.dm.categories):
            card = CategoryCard(cat, self.dm.get_today_time(cat["id"]), cat["id"] == active_cid)
            self._cards_grid.addWidget(card, i // 2, i % 2)

        # Update timer status
        if self.dm.active_session:
            cat = self.dm.get_category(self.dm.active_session["category_id"])
            self._timer_status.setText(f"{cat['name']} — активно" if cat else "Активно")
            color = cat["color"] if cat else "#7B6CF6"
            self._timer_status.setStyleSheet(f"color: {color}; font-size: 13px;")
            self._stop_btn.show()
        else:
            self._timer_status.setText("Оберіть категорію і натисни ▶")
            self._timer_status.setStyleSheet("color: #8E8E93; font-size: 13px;")
            self._timer_display.setText("00:00:00")
            self._stop_btn.hide()

        # Rebuild journal
        _clear_layout(self._journal_layout)
        sessions = self.dm.get_today_sessions()
        if sessions:
            for s in sessions[:30]:
                cat = self.dm.get_category(s["category_id"])
                if not cat:
                    continue
                row = _journal_row(cat, s)
                self._journal_layout.addWidget(row)
        else:
            empty = QLabel("Ще немає сесій сьогодні")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #48484A; font-size: 13px; padding: 20px;")
            self._journal_layout.addWidget(empty)
        self._journal_layout.addStretch()

    def _update_timer(self):
        if self.dm.active_session:
            start = datetime.fromisoformat(self.dm.active_session["start"])
            secs = int((datetime.now() - start).total_seconds())
            self._timer_display.setText(fmt_timer(secs))
            if secs % 10 == 0:
                _clear_layout(self._cards_grid)
                active_cid = self.dm.active_session["category_id"]
                for i, cat in enumerate(self.dm.categories):
                    card = CategoryCard(cat, self.dm.get_today_time(cat["id"]), cat["id"] == active_cid)
                    self._cards_grid.addWidget(card, i // 2, i % 2)

    def _on_start(self):
        idx = self._combo.currentIndex()
        if idx <= 0:
            return
        cat = self.dm.categories[idx - 1]
        self.dm.start_session(cat["id"])
        self.refresh()

    def _on_stop(self):
        self.dm.stop_session()
        self.refresh()

    def auto_start(self, category_id: str):
        if self.dm.active_session and self.dm.active_session["category_id"] == category_id:
            return
        self.dm.start_session(category_id)
        self.refresh()

    def auto_stop(self):
        if self.dm.active_session:
            self.dm.stop_session()
            self.refresh()

# ──────────────────────────── STATISTICS SCREEN ────────────────────────────

class StatisticsScreen(QWidget):
    def __init__(self, dm: DataManager):
        super().__init__()
        self.dm = dm
        self._period = "today"
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        # Period switcher
        sw = QHBoxLayout()
        sw.setSpacing(6)
        self._period_btns: dict[str, QPushButton] = {}
        for key, label in [("today", "Сьогодні"), ("week", "Тиждень"), ("month", "Місяць")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setStyleSheet("""
                QPushButton { background: #2C2C2E; border-radius: 8px; }
                QPushButton:checked { background: #7B6CF6; }
            """)
            btn.clicked.connect(lambda _, k=key: self._set_period(k))
            self._period_btns[key] = btn
            sw.addWidget(btn)
        self._period_btns["today"].setChecked(True)
        root.addLayout(sw)

        # Summary cards
        summary = QHBoxLayout()
        summary.setSpacing(8)

        f1 = QFrame()
        f1.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 12px; }")
        fl1 = QVBoxLayout(f1)
        fl1.setContentsMargins(14, 12, 14, 12)
        self._total_sm = QLabel("Всього")
        self._total_sm.setStyleSheet("color: #8E8E93; font-size: 11px;")
        self._total_big = QLabel("0г 00хв")
        self._total_big.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 600;")
        fl1.addWidget(self._total_sm)
        fl1.addWidget(self._total_big)

        f2 = QFrame()
        f2.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 12px; }")
        fl2 = QVBoxLayout(f2)
        fl2.setContentsMargins(14, 12, 14, 12)
        self._top_sm = QLabel("Найбільше")
        self._top_sm.setStyleSheet("color: #8E8E93; font-size: 11px;")
        self._top_big = QLabel("—")
        self._top_big.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 600;")
        fl2.addWidget(self._top_sm)
        fl2.addWidget(self._top_big)

        summary.addWidget(f1)
        summary.addWidget(f2)
        root.addLayout(summary)

        dist_lbl = QLabel("РОЗПОДІЛ")
        dist_lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        root.addWidget(dist_lbl)

        self._bars_widget = QWidget()
        self._bars_layout = QVBoxLayout(self._bars_widget)
        self._bars_layout.setContentsMargins(0, 0, 0, 0)
        self._bars_layout.setSpacing(10)
        root.addWidget(self._bars_widget)
        root.addStretch()

        self.refresh()

    def _set_period(self, period: str):
        self._period = period
        for k, btn in self._period_btns.items():
            btn.setChecked(k == period)
        self.refresh()

    def refresh(self):
        stats = self.dm.get_period_stats(self._period)
        total = sum(stats.values())
        self._total_big.setText(fmt_time(total))

        top_id = max(stats, key=stats.get) if any(stats.values()) else None
        if top_id:
            cat = self.dm.get_category(top_id)
            self._top_big.setText(cat["name"] if cat else "—")
        else:
            self._top_big.setText("—")

        _clear_layout(self._bars_layout)
        max_val = max(stats.values(), default=1) or 1
        for cat in self.dm.categories:
            secs = stats.get(cat["id"], 0)
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)

            name_lbl = QLabel(cat["name"])
            name_lbl.setFixedWidth(85)
            name_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")

            bar = BarWidget(secs / max_val, cat["color"])

            dur_lbl = QLabel(fmt_time(secs))
            dur_lbl.setFixedWidth(72)
            dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            dur_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")

            rl.addWidget(name_lbl)
            rl.addWidget(bar, 1)
            rl.addWidget(dur_lbl)
            self._bars_layout.addWidget(row)

        self._bars_layout.addStretch()

# ──────────────────────────── SETTINGS SCREEN ────────────────────────────

class SettingsScreen(QWidget):
    def __init__(self, dm: DataManager, on_global_refresh):
        super().__init__()
        self.dm = dm
        self._on_refresh = on_global_refresh
        self._sel_color = CATEGORY_COLORS[0]
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(14)

        # ─ Categories ─
        lay.addWidget(_section_label("КАТЕГОРІЇ"))
        self._cat_list = QWidget()
        self._cat_ll = QVBoxLayout(self._cat_list)
        self._cat_ll.setContentsMargins(0, 0, 0, 0)
        self._cat_ll.setSpacing(4)
        lay.addWidget(self._cat_list)

        add_row = QHBoxLayout()
        self._new_cat = QLineEdit()
        self._new_cat.setPlaceholderText("Назва нової категорії")
        self._color_btn = QPushButton("●")
        self._color_btn.setFixedSize(36, 36)
        self._color_btn.setStyleSheet(f"color: {self._sel_color}; font-size: 20px; background: #2C2C2E; border-radius: 8px;")
        self._color_btn.clicked.connect(self._pick_color)
        add_cat_btn = QPushButton("+ Додати")
        add_cat_btn.setObjectName("accentBtn")
        add_cat_btn.setFixedWidth(90)
        add_cat_btn.clicked.connect(self._add_category)
        add_row.addWidget(self._new_cat)
        add_row.addWidget(self._color_btn)
        add_row.addWidget(add_cat_btn)
        lay.addLayout(add_row)

        # ─ General ─
        lay.addWidget(_section_label("ЗАГАЛЬНЕ"))
        lay.addWidget(self._make_toggle("Запуск при старті системи", "autostart"))
        lay.addWidget(self._make_toggle("Нагадування (якщо таймер не активний)", "reminders"))

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self.refresh()

    def _make_toggle(self, text: str, key: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 10px; }")
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        cb = QCheckBox()
        cb.setChecked(self.dm.settings.get(key, False))
        cb.stateChanged.connect(lambda v, k=key: self._toggle(k, v))
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(cb)
        return w

    def _toggle(self, key: str, value: int):
        self.dm.settings[key] = bool(value)
        self.dm.save()

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._sel_color), self)
        if c.isValid():
            self._sel_color = c.name()
            self._color_btn.setStyleSheet(
                f"color: {self._sel_color}; font-size: 20px; background: #2C2C2E; border-radius: 8px;"
            )

    def _add_category(self):
        name = self._new_cat.text().strip()
        if not name:
            return
        self.dm.add_category(name, self._sel_color)
        self._new_cat.clear()
        self.refresh()
        self._on_refresh()

    def _edit_category(self, cat: dict):
        dlg = QDialog(self)
        dlg.setWindowTitle("Редагувати")
        dlg.setStyleSheet(STYLE)
        dlg.setMinimumWidth(280)
        ll = QVBoxLayout(dlg)
        name_edit = QLineEdit(cat["name"])
        new_color = [cat["color"]]
        color_btn = QPushButton(f"● Колір")
        color_btn.setStyleSheet(f"color: {cat['color']}; background: #2C2C2E; border-radius: 8px;")
        def pick():
            c = QColorDialog.getColor(QColor(cat["color"]), dlg)
            if c.isValid():
                new_color[0] = c.name()
                color_btn.setStyleSheet(f"color: {new_color[0]}; background: #2C2C2E; border-radius: 8px;")
        color_btn.clicked.connect(pick)
        save = QPushButton("Зберегти")
        save.setObjectName("accentBtn")
        def do_save():
            n = name_edit.text().strip()
            if n:
                cat["name"] = n
            cat["color"] = new_color[0]
            self.dm.save()
            self.refresh()
            self._on_refresh()
            dlg.accept()
        save.clicked.connect(do_save)
        ll.addWidget(QLabel("Назва:"))
        ll.addWidget(name_edit)
        ll.addWidget(color_btn)
        ll.addSpacing(8)
        ll.addWidget(save)
        dlg.exec()

    def _delete_category(self, cat: dict):
        r = QMessageBox.question(self, "Видалити?", f'Видалити "{cat["name"]}"?',
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.dm.remove_category(cat["id"])
            self.refresh()
            self._on_refresh()

    def refresh(self):
        _clear_layout(self._cat_ll)
        for cat in self.dm.categories:
            self._cat_ll.addWidget(self._cat_row(cat))

    def _cat_row(self, cat: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 8px; }")
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 8, 8, 8)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {cat['color']}; font-size: 14px; background: transparent;")
        name = QLabel(cat["name"])
        name.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        edit_btn = _icon_btn("✎", self._edit_category, cat)
        del_btn  = _icon_btn("✕", self._delete_category, cat, danger=True)
        rl.addWidget(dot)
        rl.addWidget(name)
        rl.addStretch()
        rl.addWidget(edit_btn)
        rl.addWidget(del_btn)
        return w

# ──────────────────────────── MAIN WINDOW ────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, dm: DataManager):
        super().__init__()
        self.dm = dm
        self.setWindowTitle("Трекер")
        self.setMinimumSize(440, 620)
        self.resize(480, 720)
        self.setStyleSheet(STYLE)
        self._setup_ui()
        self._setup_tray()
        self._start_tracker()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet("background: #2C2C2E;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel("Трекер")
        title_lbl.setStyleSheet("color: #FFFFFF; font-size: 17px; font-weight: 600;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(title_lbl)
        ml.addWidget(header)

        self._tracker = TrackerScreen(self.dm)
        ml.addWidget(self._tracker)


    def _setup_tray(self):
        icon_path = Path(os.path.dirname(os.path.abspath(__file__))) / "icon.ico"
        app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.setWindowIcon(app_icon)
        self._tray = QSystemTrayIcon(app_icon, self)
        self._tray.setToolTip("Tracker")
        menu = QMenu()
        menu.addAction("Відкрити", self.show)
        menu.addAction("Вийти", QApplication.instance().quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self.show() if r == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self._tray.show()

    def _start_tracker(self):
        self._wt = WindowTrackerThread()
        self._wt.window_changed.connect(self._on_window)
        self._wt.start()

    def _on_window(self, proc: str, _title: str):
        cat_id = self.dm.get_category_for_process(proc)
        if cat_id:
            self._tracker.auto_start(cat_id)
        else:
            self._tracker.auto_stop()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "Tracker", "Згорнуто в трей. ПКМ по іконці -> Вийти.",
            QSystemTrayIcon.MessageIcon.Information, 2500
        )


# ──────────────────────────── UTIL FUNCTIONS ────────────────────────────

def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
    return lbl


def _icon_btn(icon: str, callback, data, danger: bool = False) -> QPushButton:
    btn = QPushButton(icon)
    btn.setFixedSize(28, 28)
    color = "#FF453A" if danger else "#FFFFFF"
    btn.setStyleSheet(f"background: #3A3A3C; border-radius: 6px; color: {color}; font-size: 14px;")
    btn.clicked.connect(lambda: callback(data))
    return btn


def _journal_row(cat: dict, session: dict) -> QWidget:
    w = QWidget()
    w.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 8px; }")
    rl = QHBoxLayout(w)
    rl.setContentsMargins(12, 8, 12, 8)
    dot = QLabel("●")
    dot.setStyleSheet(f"color: {cat['color']}; font-size: 10px; background: transparent;")
    info = QVBoxLayout()
    n = QLabel(cat["name"])
    n.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 500; background: transparent;")
    t = QLabel(datetime.fromisoformat(session["start"]).strftime("%H:%M"))
    t.setStyleSheet("color: #8E8E93; font-size: 11px; background: transparent;")
    info.addWidget(n)
    info.addWidget(t)
    dur = QLabel(fmt_time(session["duration"]))
    dur.setStyleSheet("color: #8E8E93; font-size: 13px; background: transparent;")
    dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    rl.addWidget(dot)
    rl.addSpacing(6)
    rl.addLayout(info)
    rl.addStretch()
    rl.addWidget(dur)
    return w


# ──────────────────────────── ENTRY POINT ────────────────────────────

# Single-instance lock -- held for the entire process lifetime
import socket as _socket
_lock_sock = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
try:
    _lock_sock.bind(('127.0.0.1', 47291))
except OSError:
    sys.exit(0)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Tracker")
    dm = DataManager()
    win = MainWindow(dm)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
