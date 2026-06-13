import calendar
import csv
from datetime import date, datetime, timedelta

import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QFrame, QStackedWidget, QCheckBox, QLineEdit,
    QDialog, QListWidget, QMessageBox, QColorDialog, QFileDialog,
    QDateEdit, QTimeEdit, QSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QDate, QTime
from PyQt6.QtGui import QColor, QPainter

from styles import STYLE, CATEGORY_COLORS
from tools.common import (
    fmt_time, fmt_timer, clear_layout, section_label, icon_btn,
    is_autostart_enabled, set_autostart, format_date_ua,
)
from .manager import DataManager, UNCATEGORIZED_ID

_WEEKDAY_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]

def _fmt_compact(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}г {m:02d}хв" if m else f"{h}г"
    return f"{m}хв"

def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

ROW_BG_STYLE = "QWidget { background: #2C2C2E; border-radius: 8px; }"

DELETE_BTN_STYLE = (
    "QPushButton { background: #3A3A3C; border-radius: 6px; color: #FF453A; "
    "font-size: 12px; font-weight: 600; padding: 0px 10px; }"
    "QPushButton:hover { background: #48484A; }"
)

SECONDARY_BTN_STYLE = (
    "QPushButton { background: #3A3A3C; color: #FFFFFF; border-radius: 8px; "
    "padding: 8px; font-size: 13px; } QPushButton:hover { background: #48484A; }"
)

def _duration_spinboxes(initial_seconds: int = 0, default_minutes: int = 0):
    """Створює пару спінбоксів (год/хв) для редагування тривалості та рядок-контейнер для них."""
    hrs = QSpinBox()
    hrs.setRange(0, 23)
    hrs.setSuffix(" год")
    hrs.setValue(initial_seconds // 3600)
    mins = QSpinBox()
    mins.setRange(0, 59)
    mins.setSingleStep(5)
    mins.setValue((initial_seconds % 3600) // 60 if initial_seconds else default_minutes)
    mins.setSuffix(" хв")
    row = QHBoxLayout()
    row.addWidget(hrs)
    row.addWidget(mins)
    return hrs, mins, row

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

class CategoryCard(QFrame):
    def __init__(self, category: dict, seconds: int, active: bool = False, on_click=None,
                 goal_seconds: int | None = None, on_edit=None):
        super().__init__()
        self._cat_id = category["id"]
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if active:
            bg = _hex_to_rgba(category["color"], 0.18)
            border = category["color"]
        else:
            bg = "#2C2C2E"
            border = "#3A3A3C"
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 10px; border: 1.5px solid {border}; }}"
        )

        goal_minutes = category.get("goal_minutes") or 0
        outer = QVBoxLayout(self)
        outer.setSpacing(4)
        if goal_minutes > 0:
            outer.setContentsMargins(10, 5, 10, 6)
        else:
            outer.setContentsMargins(10, 4, 10, 4)
            self.setFixedHeight(34)

        row = QHBoxLayout()
        row.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {category['color']}; font-size: 9px; border: none; background: transparent;")
        name = QLabel(category["name"])
        name.setStyleSheet("color: #8E8E93; font-size: 11px; border: none; background: transparent;")
        row.addWidget(dot)
        row.addWidget(name)
        row.addStretch()

        time_lbl = QLabel(fmt_time(seconds))
        time_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 500; border: none; background: transparent;")
        row.addWidget(time_lbl)

        if on_edit:
            edit_btn = QPushButton("✎")
            edit_btn.setFixedSize(18, 18)
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.setToolTip("Редагувати категорію")
            edit_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; color: #8E8E93; "
                "font-size: 11px; padding: 0px; }"
                "QPushButton:hover { color: #FFFFFF; }"
            )
            edit_btn.clicked.connect(lambda _, cid=self._cat_id: on_edit(cid))
            row.addWidget(edit_btn)

        outer.addLayout(row)

        if goal_minutes > 0:
            progress = goal_seconds if goal_seconds is not None else seconds
            goal_secs = goal_minutes * 60
            ratio = progress / goal_secs if goal_secs else 0
            done = progress >= goal_secs
            bar_color = "#4CAF50" if done else category["color"]
            outer.addWidget(BarWidget(ratio, bar_color))
            period_label = {"week": "/тиждень", "month": "/місяць"}.get(category.get("goal_period", "day"), "")
            goal_text = f"Ціль: {goal_minutes} хв{period_label}" + ("  ✓" if done else f" ({fmt_time(progress)})")
            goal_lbl = QLabel(goal_text)
            goal_lbl.setStyleSheet("color: #8E8E93; font-size: 9px; border: none; background: transparent;")
            outer.addWidget(goal_lbl)

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click(self._cat_id)
        super().mousePressEvent(event)

class TrackerScreen(QWidget):
    def __init__(self, dm: DataManager, on_global_refresh=None):
        super().__init__()
        self.dm = dm
        self._on_global_refresh = on_global_refresh
        self._auto_active = False
        self._cats_expanded = False
        self._journal_expanded = False
        self._journal_limit = 15
        self._setup_ui()
        self._tick = QTimer()
        self._tick.timeout.connect(self._update_timer)
        self._tick.start(1000)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        tab_row = QHBoxLayout()
        tab_row.setSpacing(6)
        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(["Ручний", "Авто", "Статист.", "Налашт."]):
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
        self._stats_page = StatisticsScreen(self.dm, self._global_refresh)
        self._tab_stack.addWidget(self._stats_page)
        self._settings_page = SettingsScreen(self.dm, self._global_refresh)
        self._tab_stack.addWidget(self._settings_page)
        root.addWidget(self._tab_stack)

        self.refresh()

    def _global_refresh(self):
        self.refresh()
        self._stats_page.refresh()
        self._refresh_auto()
        self._settings_page.refresh()
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

    def _build_manual_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(7)

        lbl = QLabel("СЬОГОДНІ")
        lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
        lay.addWidget(lbl)

        self._cards_container = QWidget()
        self._cards_grid = QGridLayout(self._cards_container)
        self._cards_grid.setSpacing(6)
        self._cards_grid.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._cards_container)

        self._cats_toggle_btn = QPushButton()
        self._cats_toggle_btn.setFlat(True)
        self._cats_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cats_toggle_btn.setStyleSheet(
            "QPushButton { color: #7B6CF6; font-size: 11px; font-weight: 600; "
            "text-align: left; background: transparent; border: none; padding: 0px; }"
        )
        self._cats_toggle_btn.clicked.connect(self._toggle_categories)
        self._cats_toggle_btn.hide()
        lay.addWidget(self._cats_toggle_btn)

        timer_frame = QFrame()
        timer_frame.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; }")
        timer_frame.setMinimumHeight(90)
        tl = QVBoxLayout(timer_frame)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setSpacing(6)

        self._timer_status = QLabel("Натисніть на категорію щоб почати")
        self._timer_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_status.setStyleSheet("color: #8E8E93; font-size: 13px;")

        self._timer_display = QLabel("00:00:00")
        self._timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_display.setStyleSheet(
            "color: #FFFFFF; font-size: 36px; font-weight: 300; font-family: 'Courier New', monospace;"
        )

        tl.addWidget(self._timer_status)
        tl.addWidget(self._timer_display)
        lay.addWidget(timer_frame)

        journal_row = QHBoxLayout()
        journal_row.setContentsMargins(0, 0, 0, 0)
        self._journal_toggle_btn = QPushButton("ЖУРНАЛ  ▸")
        self._journal_toggle_btn.setFlat(True)
        self._journal_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._journal_toggle_btn.setStyleSheet(
            "QPushButton { color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px; "
            "text-align: left; background: transparent; border: none; padding: 0px; }"
        )
        self._journal_toggle_btn.clicked.connect(self._toggle_journal)
        journal_row.addWidget(self._journal_toggle_btn)
        journal_row.addStretch()

        add_session_btn = QPushButton("+ Додати запис")
        add_session_btn.setFlat(True)
        add_session_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_session_btn.setStyleSheet(
            "QPushButton { color: #7B6CF6; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none; padding: 0px; }"
        )
        add_session_btn.clicked.connect(self._add_manual_session_dialog)
        journal_row.addWidget(add_session_btn)
        lay.addLayout(journal_row)

        self._journal_filter_widget = QWidget()
        filter_row = QHBoxLayout(self._journal_filter_widget)
        filter_row.setContentsMargins(0, 0, 0, 0)
        self._journal_search = QLineEdit()
        self._journal_search.setPlaceholderText("Пошук за категорією або нотаткою…")
        self._journal_search.textChanged.connect(self._on_journal_filter_changed)
        self._journal_cat_filter = QComboBox()
        self._journal_cat_filter.setFixedWidth(140)
        self._journal_cat_filter.currentIndexChanged.connect(self._on_journal_filter_changed)
        filter_row.addWidget(self._journal_search, 1)
        filter_row.addWidget(self._journal_cat_filter)
        self._journal_filter_widget.setVisible(self._journal_expanded)
        lay.addWidget(self._journal_filter_widget)

        self._journal_inner = QWidget()
        self._journal_layout = QVBoxLayout(self._journal_inner)
        self._journal_layout.setContentsMargins(0, 0, 0, 0)
        self._journal_layout.setSpacing(4)

        self._journal_scroll = QScrollArea()
        self._journal_scroll.setWidget(self._journal_inner)
        self._journal_scroll.setWidgetResizable(True)
        self._journal_scroll.setVisible(self._journal_expanded)
        lay.addWidget(self._journal_scroll)
        lay.addStretch()

        return page

    def _build_auto_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 4, 0, 0)

        cols = QHBoxLayout()
        cols.setSpacing(12)
        outer.addLayout(cols)

        # ---------- Ліва колонка: програми, які відстежуються ----------
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 8, 0)
        left_lay.setSpacing(10)

        left_lay.addWidget(section_label("ПРОГРАМИ"))
        self._auto_map_widget = QWidget()
        self._auto_map_layout = QVBoxLayout(self._auto_map_widget)
        self._auto_map_layout.setContentsMargins(0, 0, 0, 0)
        self._auto_map_layout.setSpacing(4)
        left_lay.addWidget(self._auto_map_widget)

        left_lay.addWidget(section_label("СЬОГОДНІ БЕЗ КАТЕГОРІЇ"))
        uncat_hint = QLabel(
            "Активність без призначеної категорії відстежується автоматично. "
            "Призначте категорію — і записи за сьогодні теж перенесуться."
        )
        uncat_hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        uncat_hint.setWordWrap(True)
        left_lay.addWidget(uncat_hint)

        self._uncat_widget = QWidget()
        self._uncat_layout = QVBoxLayout(self._uncat_widget)
        self._uncat_layout.setContentsMargins(0, 0, 0, 0)
        self._uncat_layout.setSpacing(4)
        left_lay.addWidget(self._uncat_widget)
        left_lay.addStretch()

        left_scroll = QScrollArea()
        left_scroll.setWidget(left_widget)
        left_scroll.setWidgetResizable(True)
        cols.addWidget(left_scroll, 1)

        # ---------- Права колонка ----------
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)
        right_lay.setContentsMargins(8, 0, 0, 0)
        right_lay.setSpacing(10)

        # Зверху: ігнор-лист
        right_lay.addWidget(section_label("ІГНОР-ЛИСТ"))
        ignore_hint = QLabel("Процеси з цього списку ніколи не відстежуються автоматично.")
        ignore_hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        ignore_hint.setWordWrap(True)
        right_lay.addWidget(ignore_hint)

        ignore_row = QHBoxLayout()
        self._ignore_proc_input = QLineEdit()
        self._ignore_proc_input.setPlaceholderText("Назва процесу (напр. Discord.exe)")
        ignore_add_btn = QPushButton("+ Додати")
        ignore_add_btn.setObjectName("accentBtn")
        ignore_add_btn.setFixedWidth(90)
        ignore_add_btn.clicked.connect(self._add_ignored_process)
        ignore_row.addWidget(self._ignore_proc_input)
        ignore_row.addWidget(ignore_add_btn)
        right_lay.addLayout(ignore_row)

        self._ignore_list_widget = QWidget()
        self._ignore_list_layout = QVBoxLayout(self._ignore_list_widget)
        self._ignore_list_layout.setContentsMargins(0, 0, 0, 0)
        self._ignore_list_layout.setSpacing(4)

        ignore_scroll = QScrollArea()
        ignore_scroll.setWidgetResizable(True)
        ignore_scroll.setFrameShape(QFrame.Shape.NoFrame)
        ignore_scroll.setFixedHeight(220)
        ignore_scroll.setWidget(self._ignore_list_widget)
        right_lay.addWidget(ignore_scroll)

        right_lay.addSpacing(6)

        # Знизу: додати окремий процес
        right_lay.addWidget(section_label("ДОДАТИ ПРОЦЕС"))
        self._auto_proc_input = QLineEdit()
        self._auto_proc_input.setPlaceholderText("Назва процесу (напр. chrome.exe)")
        right_lay.addWidget(self._auto_proc_input)

        self._auto_title_input = QLineEdit()
        self._auto_title_input.setPlaceholderText("Заголовок вікна містить (необов'язково)")
        right_lay.addWidget(self._auto_title_input)

        add_row = QHBoxLayout()
        self._auto_cat_combo = QComboBox()
        add_btn = QPushButton("+ Додати")
        add_btn.setObjectName("accentBtn")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_auto_mapping)
        add_row.addWidget(self._auto_cat_combo)
        add_row.addWidget(add_btn)
        right_lay.addLayout(add_row)

        running_btn = QPushButton("📋  Показати запущені процеси")
        running_btn.clicked.connect(lambda: self._show_running_auto(self._auto_proc_input))
        right_lay.addWidget(running_btn)

        right_lay.addStretch()
        cols.addWidget(right_widget, 1)

        return page

    def _refresh_auto(self):
        clear_layout(self._auto_map_layout)
        mappings = self.dm.app_mappings
        if not mappings:
            hint = QLabel("Немає програм. Додай процес → категорія.")
            hint.setStyleSheet("color: #48484A; font-size: 12px; padding: 4px;")
            self._auto_map_layout.addWidget(hint)
        else:
            by_cat: dict[str, list] = {}
            for m in mappings:
                by_cat.setdefault(m["category_id"], []).append(m)
            ordered_ids = [c["id"] for c in self.dm.all_categories if c["id"] in by_cat]
            ordered_ids += [cid for cid in by_cat if cid not in ordered_ids]
            for cid in ordered_ids:
                cat = self.dm.get_category(cid)
                header = QLabel(cat["name"] if cat else "?")
                color = cat["color"] if cat else "#888"
                header.setStyleSheet(
                    f"color: {color}; font-size: 12px; font-weight: 600; padding: 4px 2px 0px 2px; background: transparent;"
                )
                self._auto_map_layout.addWidget(header)
                for m in by_cat[cid]:
                    self._auto_map_layout.addWidget(self._auto_map_row(m))
        self._auto_map_layout.addStretch()
        self._auto_cat_options = [c for c in self.dm.categories if c["id"] != UNCATEGORIZED_ID]
        self._auto_cat_combo.clear()
        for cat in self._auto_cat_options:
            self._auto_cat_combo.addItem(cat["name"])

        clear_layout(self._uncat_layout)
        breakdown = self.dm.get_uncategorized_breakdown()
        if breakdown:
            for proc, secs in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
                self._uncat_layout.addWidget(self._uncat_row(proc, secs))
        else:
            hint = QLabel("Усе сьогоднішнє автоматичне відстеження вже категоризоване.")
            hint.setStyleSheet("color: #48484A; font-size: 12px; padding: 4px;")
            hint.setWordWrap(True)
            self._uncat_layout.addWidget(hint)

        clear_layout(self._ignore_list_layout)
        for proc in self.dm.ignored_processes:
            self._ignore_list_layout.addWidget(self._ignore_row(proc))
        if not self.dm.ignored_processes:
            hint = QLabel("Список порожній.")
            hint.setStyleSheet("color: #48484A; font-size: 12px; padding: 4px;")
            self._ignore_list_layout.addWidget(hint)

    def _uncat_row(self, proc: str, secs: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet(ROW_BG_STYLE)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)

        top = QHBoxLayout()
        proc_lbl = QLabel(proc)
        proc_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        time_lbl = QLabel(fmt_time(secs))
        time_lbl.setStyleSheet("color: #8E8E93; font-size: 11px; background: transparent;")
        top.addWidget(proc_lbl)
        top.addStretch()
        top.addWidget(time_lbl)
        outer.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)

        cat_combo = QComboBox()
        options = [c for c in self.dm.categories if c["id"] != UNCATEGORIZED_ID]
        for cat in options:
            cat_combo.addItem(cat["name"])
        bottom.addWidget(cat_combo, 1)

        assign_btn = QPushButton("✓")
        assign_btn.setFixedSize(28, 28)
        assign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        assign_btn.setToolTip("Призначити категорію")
        assign_btn.setStyleSheet(
            "QPushButton { background: #7B6CF6; border-radius: 6px; color: #FFFFFF; "
            "font-size: 14px; font-weight: 700; padding: 0px; }"
            "QPushButton:hover { background: #8E7FF8; }"
        )

        def do_assign(_=None, p=proc, opts=options, combo=cat_combo):
            if combo.count() == 0:
                return
            cat = opts[combo.currentIndex()]
            self.dm.assign_process_category(p, cat["id"])
            self._global_refresh()

        assign_btn.clicked.connect(do_assign)
        bottom.addWidget(assign_btn)

        ignore_btn = QPushButton("✕")
        ignore_btn.setFixedSize(28, 28)
        ignore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ignore_btn.setToolTip("Не відстежувати цей процес")
        ignore_btn.setStyleSheet(
            "QPushButton { background: #3A3A3C; border-radius: 6px; color: #FF453A; "
            "font-size: 14px; font-weight: 700; padding: 0px; }"
            "QPushButton:hover { background: #48484A; }"
        )
        ignore_btn.clicked.connect(lambda _, p=proc: (self.dm.add_ignored_process(p), self._global_refresh()))
        bottom.addWidget(ignore_btn)

        outer.addLayout(bottom)
        return w

    def _ignore_row(self, proc: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet(ROW_BG_STYLE)
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 6, 8, 6)
        lbl = QLabel(proc)
        lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        del_btn = QPushButton("Видалити")
        del_btn.setFixedHeight(28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Видалити з ігнор-листа")
        del_btn.setStyleSheet(DELETE_BTN_STYLE)
        del_btn.clicked.connect(lambda _, p=proc: (self.dm.remove_ignored_process(p), self._refresh_auto()))
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(del_btn)
        return w

    def _add_ignored_process(self):
        proc = self._ignore_proc_input.text().strip()
        if not proc:
            return
        self.dm.add_ignored_process(proc)
        self._ignore_proc_input.clear()
        self._refresh_auto()

    def _auto_map_row(self, m: dict) -> QWidget:
        title_contains = m.get("title_contains", "")
        w = QWidget()
        w.setStyleSheet(ROW_BG_STYLE)
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 8, 8, 8)

        info = QVBoxLayout()
        info.setSpacing(2)
        proc_lbl = QLabel(m["process"])
        proc_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        info.addWidget(proc_lbl)
        if title_contains:
            title_lbl = QLabel(f'заголовок: "{title_contains}"')
            title_lbl.setStyleSheet("color: #8E8E93; font-size: 10px; background: transparent;")
            info.addWidget(title_lbl)

        del_btn = QPushButton("Видалити")
        del_btn.setFixedHeight(28)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setToolTip("Видалити правило")
        del_btn.setStyleSheet(DELETE_BTN_STYLE)
        del_btn.clicked.connect(
            lambda _, proc=m["process"], tc=title_contains: (self.dm.remove_mapping(proc, tc), self._refresh_auto())
        )
        rl.addLayout(info)
        rl.addStretch()
        rl.addWidget(del_btn)
        return w

    def _add_auto_mapping(self):
        proc = self._auto_proc_input.text().strip()
        if not proc or self._auto_cat_combo.count() == 0:
            return
        title = self._auto_title_input.text().strip()
        cat = self._auto_cat_options[self._auto_cat_combo.currentIndex()]
        self.dm.add_mapping(proc, cat["id"], title)
        self._auto_proc_input.clear()
        self._auto_title_input.clear()
        self._refresh_auto()

    def _show_running_auto(self, target_input=None):
        target_input = target_input or self._auto_proc_input
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
                target_input.setText(items[0].text())
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
        self._refresh_cards()

        if self.dm.active_session:
            cat = self.dm.get_category(self.dm.active_session["category_id"])
            self._timer_status.setText(f"{cat['name']} — активно" if cat else "Активно")
            color = cat["color"] if cat else "#7B6CF6"
            self._timer_status.setStyleSheet(f"color: {color}; font-size: 13px;")
        else:
            self._timer_status.setText("Натисніть на категорію щоб почати")
            self._timer_status.setStyleSheet("color: #8E8E93; font-size: 13px;")
            self._timer_display.setText("00:00:00")

        self._refresh_journal_cat_filter()
        self._refresh_journal()

    def _refresh_journal_cat_filter(self):
        combo = self._journal_cat_filter
        prev_id = combo.currentData() if combo.count() else None
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Усі категорії", None)
        for cat in self.dm.categories:
            combo.addItem(cat["name"], cat["id"])
        idx = combo.findData(prev_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _on_journal_filter_changed(self, *_args):
        self._journal_limit = 15
        self._refresh_journal()

    def _refresh_journal(self):
        clear_layout(self._journal_layout)
        sessions = self.dm.get_today_sessions()
        text = self._journal_search.text().strip().lower()
        cat_filter_id = self._journal_cat_filter.currentData()

        filtered = []
        for s in sessions:
            cat = self.dm.get_category(s["category_id"])
            if not cat:
                continue
            if cat_filter_id and s["category_id"] != cat_filter_id:
                continue
            if text:
                haystack = (cat["name"] + " " + s.get("note", "")).lower()
                if text not in haystack:
                    continue
            filtered.append((cat, s))

        if filtered:
            for cat, s in filtered[:self._journal_limit]:
                row = _journal_row(cat, s, lambda sess=s: self._edit_session_dialog(sess))
                self._journal_layout.addWidget(row)
            if len(filtered) > self._journal_limit:
                more_btn = QPushButton(f"Показати ще ({len(filtered) - self._journal_limit})")
                more_btn.setFlat(True)
                more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                more_btn.setStyleSheet(
                    "QPushButton { color: #7B6CF6; font-size: 12px; font-weight: 600; "
                    "background: transparent; border: none; padding: 6px; }"
                )
                more_btn.clicked.connect(self._show_more_journal)
                self._journal_layout.addWidget(more_btn)
        else:
            msg = "Нічого не знайдено" if (text or cat_filter_id) else "Ще немає сесій сьогодні"
            empty = QLabel(msg)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #48484A; font-size: 13px; padding: 20px;")
            self._journal_layout.addWidget(empty)
        self._journal_layout.addStretch()

    def _show_more_journal(self):
        self._journal_limit += 15
        self._refresh_journal()

    def _refresh_cards(self):
        clear_layout(self._cards_grid)
        active_cid = self.dm.active_session["category_id"] if self.dm.active_session else None
        cats_sorted = sorted(
            self.dm.categories, key=lambda c: self.dm.get_today_time(c["id"]), reverse=True
        )
        visible = cats_sorted if self._cats_expanded else cats_sorted[:8]
        for i, cat in enumerate(visible):
            today_secs = self.dm.get_today_time(cat["id"])
            period = cat.get("goal_period", "day")
            goal_secs = self.dm.get_period_time(cat["id"], period) if period != "day" else None
            card = CategoryCard(cat, today_secs, cat["id"] == active_cid, self._on_card_click,
                                 goal_secs, self._edit_category_dialog)
            self._cards_grid.addWidget(card, i // 2, i % 2)

        extra = len(cats_sorted) - 8
        if extra > 0:
            self._cats_toggle_btn.setText("Згорнути  ▴" if self._cats_expanded else f"Ще {extra}  ▾")
            self._cats_toggle_btn.show()
        else:
            self._cats_toggle_btn.hide()

    def _toggle_categories(self):
        self._cats_expanded = not self._cats_expanded
        self._refresh_cards()

    def _edit_category_dialog(self, cat_id: str):
        cat = self.dm.get_category(cat_id)
        if not cat:
            return
        _open_edit_category_dialog(self, self.dm, cat, self._global_refresh)

    def _on_card_click(self, cat_id: str):
        self._auto_active = False
        if self.dm.active_session and self.dm.active_session["category_id"] == cat_id:
            self.dm.stop_session()
        else:
            self.dm.start_session(cat_id)
        self.refresh()

    def _toggle_journal(self):
        self._journal_expanded = not self._journal_expanded
        self._journal_scroll.setVisible(self._journal_expanded)
        self._journal_filter_widget.setVisible(self._journal_expanded)
        self._journal_toggle_btn.setText(f"ЖУРНАЛ  {'▾' if self._journal_expanded else '▸'}")

    def _add_manual_session_dialog(self):
        if not self.dm.categories:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Додати запис")
        dlg.setStyleSheet(STYLE)
        dlg.setMinimumWidth(280)
        ll = QVBoxLayout(dlg)

        ll.addWidget(QLabel("Категорія:"))
        cat_combo = QComboBox()
        for cat in self.dm.categories:
            cat_combo.addItem(cat["name"])
        ll.addWidget(cat_combo)

        ll.addWidget(QLabel("Дата:"))
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("dd.MM.yyyy")
        date_edit.setMaximumDate(QDate.currentDate())
        date_edit.setDate(QDate.currentDate())
        ll.addWidget(date_edit)

        ll.addWidget(QLabel("Час початку:"))
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        time_edit.setTime(QTime.currentTime())
        ll.addWidget(time_edit)

        ll.addWidget(QLabel("Тривалість:"))
        hrs, mins, dur_row = _duration_spinboxes(default_minutes=30)
        ll.addLayout(dur_row)

        ll.addWidget(QLabel("Нотатка (необов'язково):"))
        note_edit = QLineEdit()
        note_edit.setPlaceholderText("напр. перерва на 30 хв")
        ll.addWidget(note_edit)

        save = QPushButton("Додати")
        save.setObjectName("accentBtn")

        def do_save():
            cat = self.dm.categories[cat_combo.currentIndex()]
            duration = hrs.value() * 3600 + mins.value() * 60
            if duration <= 0:
                QMessageBox.warning(dlg, "Помилка", "Тривалість має бути більшою за 0")
                return
            d = date_edit.date().toPyDate()
            t = time_edit.time().toPyTime()
            start = datetime.combine(d, t)
            self.dm.add_manual_session(cat["id"], start, duration, note_edit.text())
            self._global_refresh()
            dlg.accept()

        save.clicked.connect(do_save)
        ll.addSpacing(8)
        ll.addWidget(save)
        dlg.exec()

    def _edit_session_dialog(self, session: dict):
        _open_edit_session_dialog(self, self.dm, session, self._global_refresh)

    def _update_timer(self):
        if self.dm.active_session:
            start = datetime.fromisoformat(self.dm.active_session["start"])
            secs = int((datetime.now() - start).total_seconds())
            self._timer_display.setText(fmt_timer(secs))
            if secs % 60 == 0:
                self._refresh_cards()

    def auto_start(self, category_id: str, process: str | None = None):
        active = self.dm.active_session
        if active:
            if not self._auto_active:
                return
            same_cat = active["category_id"] == category_id
            same_proc = active.get("process") == process
            if same_cat and (category_id != UNCATEGORIZED_ID or same_proc):
                return
        self._auto_active = True
        self.dm.start_session(category_id, process=process)
        self.refresh()

class DayCell(QFrame):
    def __init__(self, day: date, seconds: int, is_today: bool, on_click):
        super().__init__()
        self._day = day
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        border = "#7B6CF6" if is_today else "#3A3A3C"
        self.setStyleSheet(
            f"QFrame {{ background: #2C2C2E; border-radius: 10px; border: 1.5px solid {border}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(4)

        wd = QLabel(_WEEKDAY_SHORT[day.weekday()])
        wd.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wd.setStyleSheet("color: #8E8E93; font-size: 10px; border: none;")
        lay.addWidget(wd)

        num = QLabel(str(day.day))
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet("color: #FFFFFF; font-size: 13px; font-weight: 600; border: none;")
        lay.addWidget(num)

        t = QLabel(_fmt_compact(seconds))
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet("color: #7B6CF6; font-size: 10px; font-weight: 600; border: none;")
        lay.addWidget(t)

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click(self._day)
        super().mousePressEvent(event)

class _ClickableRow(QWidget):
    def __init__(self, on_click, cat_id: str):
        super().__init__()
        self._on_click = on_click
        self._cat_id = cat_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if self._on_click:
            self._on_click(self._cat_id)
        super().mousePressEvent(event)

class StatisticsScreen(QWidget):
    def __init__(self, dm: DataManager, on_global_refresh=None):
        super().__init__()
        self.dm = dm
        self._on_global_refresh = on_global_refresh
        self._period = "day"
        self._day = date.today()
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        sw = QHBoxLayout()
        sw.setSpacing(6)
        self._period_btns: dict[str, QPushButton] = {}
        for key, label in [("day", "День"), ("month", "Місяць")]:
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
        self._period_btns["day"].setChecked(True)

        sw.addStretch()
        export_btn = QPushButton("⬇ CSV")
        export_btn.setFixedHeight(32)
        export_btn.setToolTip("Експортувати статистику у CSV")
        export_btn.clicked.connect(self._export_csv)
        sw.addWidget(export_btn)

        root.addLayout(sw)

        self._day_nav = QWidget()
        nav = QHBoxLayout(self._day_nav)
        nav.setContentsMargins(0, 0, 0, 0)
        nav.addWidget(icon_btn("◀", self._shift_day, -1))
        self._day_lbl = QLabel()
        self._day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._day_lbl.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 600;")
        nav.addWidget(self._day_lbl, 1)
        nav.addWidget(icon_btn("▶", self._shift_day, 1))
        today_btn = QPushButton("Сьогодні")
        today_btn.clicked.connect(self._goto_today)
        nav.addWidget(today_btn)
        root.addWidget(self._day_nav)

        self._month_grid = QWidget()
        self._month_grid_layout = QGridLayout(self._month_grid)
        self._month_grid_layout.setContentsMargins(0, 0, 0, 0)
        self._month_grid_layout.setSpacing(4)
        root.addWidget(self._month_grid)

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

    def _shift_day(self, delta: int):
        self._day += timedelta(days=delta)
        self.refresh()

    def _goto_today(self):
        self._day = date.today()
        self.refresh()

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Експорт статистики", f"tracker_{date.today().isoformat()}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        try:
            sessions = sorted(
                (s for s in self.dm.sessions if s.get("end")),
                key=lambda s: s["start"]
            )
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Дата", "Категорія", "Початок", "Кінець", "Тривалість (с)", "Тривалість"])
                for s in sessions:
                    cat = self.dm.get_category(s["category_id"])
                    start = datetime.fromisoformat(s["start"])
                    end = datetime.fromisoformat(s["end"])
                    writer.writerow([
                        start.strftime("%Y-%m-%d"),
                        cat["name"] if cat else s["category_id"],
                        start.strftime("%H:%M:%S"),
                        end.strftime("%H:%M:%S"),
                        s["duration"],
                        fmt_time(s["duration"]),
                    ])
            QMessageBox.information(self, "Готово", f"Статистику збережено:\n{path}")
        except Exception as ex:
            QMessageBox.warning(self, "Помилка", f"Не вдалося зберегти файл:\n{ex}")

    def refresh(self):
        self._day_nav.setVisible(self._period == "day")
        self._month_grid.setVisible(self._period == "month")

        if self._period == "day":
            self._day_lbl.setText(format_date_ua(self._day))
            stats = self.dm.get_day_stats(self._day.isoformat())
        else:
            self._refresh_month_grid()
            stats = self.dm.get_period_stats("month")
        total = sum(stats.values())
        self._total_big.setText(fmt_time(total))

        top_id = max(stats, key=stats.get) if any(stats.values()) else None
        if top_id:
            cat = self.dm.get_category(top_id)
            self._top_big.setText(cat["name"] if cat else "—")
        else:
            self._top_big.setText("—")

        self._populate_bars(self._bars_layout, stats)

    def _populate_bars(self, layout, stats, on_click=None):
        clear_layout(layout)
        max_val = max(stats.values(), default=1) or 1
        cats = list(self.dm.categories)
        cats += [c for c in self.dm.all_categories if c.get("archived") and stats.get(c["id"], 0) > 0]
        cats_sorted = sorted(cats, key=lambda c: stats.get(c["id"], 0), reverse=True)
        for cat in cats_sorted:
            secs = stats.get(cat["id"], 0)
            row = _ClickableRow(on_click, cat["id"]) if on_click else QWidget()
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
            layout.addWidget(row)

        layout.addStretch()

    def _refresh_month_grid(self):
        clear_layout(self._month_grid_layout)
        today = date.today()
        first = today.replace(day=1)
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        for col, label in enumerate(_WEEKDAY_SHORT):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #8E8E93; font-size: 10px; font-weight: 600;")
            self._month_grid_layout.addWidget(lbl, 0, col)

        row = 1
        col = first.weekday()
        for day_num in range(1, days_in_month + 1):
            day = date(today.year, today.month, day_num)
            day_stats = self.dm.get_day_stats(day.isoformat())
            cell = DayCell(day, sum(day_stats.values()), day == today, self._show_day_detail)
            self._month_grid_layout.addWidget(cell, row, col)
            col += 1
            if col > 6:
                col = 0
                row += 1

    def _notify_changed(self):
        if self._on_global_refresh:
            self._on_global_refresh()
        else:
            self.refresh()

    def _show_day_detail(self, day: date):
        stats = self.dm.get_day_stats(day.isoformat())
        total = sum(stats.values())

        dlg = QDialog(self)
        dlg.setStyleSheet(STYLE)
        dlg.setWindowTitle(format_date_ua(day))
        dlg.setMinimumWidth(320)

        lay = QVBoxLayout(dlg)
        lay.setSpacing(10)

        title = QLabel(format_date_ua(day))
        title.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 600;")
        lay.addWidget(title)

        total_lbl = QLabel(f"Всього: {fmt_time(total)}")
        total_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        lay.addWidget(total_lbl)

        hint_lbl = QLabel("Натисни на категорію, щоб змінити її час")
        hint_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        lay.addWidget(hint_lbl)

        bars_widget = QWidget()
        bars_layout = QVBoxLayout(bars_widget)
        bars_layout.setContentsMargins(0, 0, 0, 0)
        bars_layout.setSpacing(10)
        lay.addWidget(bars_widget)

        def reopen():
            dlg.accept()
            self._show_day_detail(day)

        def on_done():
            self._notify_changed()
            reopen()

        def on_bar_click(cat_id: str):
            cur_stats = self.dm.get_day_stats(day.isoformat())
            _open_edit_day_category_dialog(self, self.dm, day, cat_id, cur_stats.get(cat_id, 0), on_done)

        self._populate_bars(bars_layout, stats, on_click=on_bar_click)

        close_btn = QPushButton("Закрити")
        close_btn.setObjectName("accentBtn")
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)

        dlg.exec()

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

        lay.addWidget(section_label("КАТЕГОРІЇ"))
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
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setStyleSheet(
            f"QPushButton {{ color: {self._sel_color}; font-size: 20px; background: #2C2C2E; "
            f"border-radius: 8px; padding: 0px; }}"
        )
        self._color_btn.clicked.connect(self._pick_color)
        add_cat_btn = QPushButton("+ Додати")
        add_cat_btn.setObjectName("accentBtn")
        add_cat_btn.setFixedWidth(90)
        add_cat_btn.clicked.connect(self._add_category)
        add_row.addWidget(self._new_cat)
        add_row.addWidget(self._color_btn)
        add_row.addWidget(add_cat_btn)
        lay.addLayout(add_row)

        lay.addWidget(section_label("ЗАГАЛЬНЕ"))
        lay.addWidget(self._make_toggle("Запуск при старті системи", "autostart"))
        lay.addWidget(self._make_toggle_with_spin(
            "Нагадування, якщо таймер неактивний понад", "reminders",
            "reminder_idle_min", 30, "хв", 1, 240
        ))
        lay.addWidget(self._make_toggle_with_spin(
            "Авто-пауза при бездіяльності понад", "idle_detection",
            "idle_threshold_min", 5, "хв", 1, 60
        ))

        lay.addWidget(section_label("ДАНІ"))
        data_row = QHBoxLayout()
        export_btn = QPushButton("⬇ Експорт даних")
        export_btn.clicked.connect(self._export_data)
        import_btn = QPushButton("⬆ Імпорт даних")
        import_btn.clicked.connect(self._import_data)
        data_row.addWidget(export_btn)
        data_row.addWidget(import_btn)
        lay.addLayout(data_row)
        hint = QLabel("Експорт зберігає всі категорії, сесії та налаштування трекера у файл. "
                       "Імпорт повністю замінює поточні дані вмістом файлу.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        lay.addWidget(hint)

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
        if key == "autostart":
            checked = is_autostart_enabled()
            if self.dm.settings.get(key) != checked:
                self.dm.settings[key] = checked
                self.dm.save()
        else:
            checked = self.dm.settings.get(key, False)
        cb.setChecked(checked)
        cb.stateChanged.connect(lambda v, k=key: self._toggle(k, v))
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(cb)
        return w

    def _make_toggle_with_spin(self, text: str, toggle_key: str, spin_key: str,
                                default_val: int, suffix: str, min_v: int, max_v: int) -> QWidget:
        w = QWidget()
        w.setStyleSheet("QWidget { background: #2C2C2E; border-radius: 10px; }")
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        lbl.setWordWrap(True)

        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSuffix(f" {suffix}")
        spin.setFixedWidth(90)
        spin.setValue(self.dm.settings.get(spin_key, default_val))
        spin.valueChanged.connect(lambda v, k=spin_key: self._set_setting(k, v))

        cb = QCheckBox()
        cb.setChecked(self.dm.settings.get(toggle_key, False))
        cb.stateChanged.connect(lambda v, k=toggle_key: self._toggle(k, v))

        rl.addWidget(lbl, 1)
        rl.addWidget(spin)
        rl.addWidget(cb)
        return w

    def _set_setting(self, key: str, value):
        self.dm.settings[key] = value
        self.dm.save()

    def _toggle(self, key: str, value: int):
        value = bool(value)
        self.dm.settings[key] = value
        self.dm.save()
        if key == "autostart":
            set_autostart(value)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self._sel_color), self)
        if c.isValid():
            self._sel_color = c.name()
            self._color_btn.setStyleSheet(
                f"QPushButton {{ color: {self._sel_color}; font-size: 20px; background: #2C2C2E; "
                f"border-radius: 8px; padding: 0px; }}"
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
        def on_done():
            self.refresh()
            self._on_refresh()
        _open_edit_category_dialog(self, self.dm, cat, on_done)

    def _delete_category(self, cat: dict):
        r = QMessageBox.question(self, "Видалити?", f'Видалити "{cat["name"]}"?',
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self.dm.remove_category(cat["id"])
            self.refresh()
            self._on_refresh()

    def _export_data(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Експорт даних трекера",
            f"tracker_backup_{date.today().isoformat()}.json", "JSON (*.json)"
        )
        if not path:
            return
        try:
            self.dm.export_data(path)
            QMessageBox.information(self, "Готово", f"Дані збережено у файл:\n{path}")
        except Exception as ex:
            QMessageBox.warning(self, "Помилка", f"Не вдалося зберегти файл:\n{ex}")

    def _import_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Імпорт даних трекера", "", "JSON (*.json)")
        if not path:
            return
        r = QMessageBox.question(
            self, "Імпортувати дані?",
            "Це повністю замінить поточні категорії, сесії та налаштування трекера "
            "вмістом обраного файлу. Продовжити?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            self.dm.import_data(path)
            self._on_refresh()
            self.refresh()
            QMessageBox.information(self, "Готово", "Дані трекера імпортовано.")
        except Exception as ex:
            QMessageBox.warning(self, "Помилка", f"Не вдалося завантажити файл:\n{ex}")

    def refresh(self):
        clear_layout(self._cat_ll)
        for cat in self.dm.categories:
            self._cat_ll.addWidget(self._cat_row(cat))

    def _cat_row(self, cat: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet(ROW_BG_STYLE)
        rl = QHBoxLayout(w)
        rl.setContentsMargins(12, 8, 8, 8)
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {cat['color']}; font-size: 14px; background: transparent;")
        name = QLabel(cat["name"])
        name.setStyleSheet("color: #FFFFFF; font-size: 13px; background: transparent;")
        edit_btn = icon_btn("✎", self._edit_category, cat)
        rl.addWidget(dot)
        rl.addWidget(name)
        rl.addStretch()
        rl.addWidget(edit_btn)
        if cat["id"] != UNCATEGORIZED_ID:
            del_btn = icon_btn("✕", self._delete_category, cat, danger=True)
            rl.addWidget(del_btn)
        return w

class _JournalRow(QWidget):
    """Рядок журналу. Якщо передано on_click — стає клікабельним (відкриває редагування)."""
    def __init__(self, on_click=None):
        super().__init__()
        self._on_click = on_click
        if on_click:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if self._on_click and event.button() == Qt.MouseButton.LeftButton:
            self._on_click()
        super().mousePressEvent(event)

def _journal_row(cat: dict, session: dict, on_click=None) -> QWidget:
    w = _JournalRow(on_click)
    w.setStyleSheet(ROW_BG_STYLE)
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
    if session.get("note"):
        note_lbl = QLabel(session["note"])
        note_lbl.setStyleSheet("color: #636366; font-size: 11px; font-style: italic; background: transparent;")
        note_lbl.setWordWrap(False)
        fm = note_lbl.fontMetrics()
        note_lbl.setMaximumWidth(260)
        if fm.horizontalAdvance(session["note"]) > 260:
            elided = fm.elidedText(session["note"], Qt.TextElideMode.ElideRight, 260)
            note_lbl.setText(elided)
            note_lbl.setToolTip(session["note"])
        info.addWidget(note_lbl)
    dur = QLabel(fmt_time(session["duration"]))
    dur.setStyleSheet("color: #8E8E93; font-size: 13px; background: transparent;")
    dur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    if on_click:
        edit_hint = QLabel("✎")
        edit_hint.setStyleSheet("color: #48484A; font-size: 12px; background: transparent;")
        rl.addWidget(dot)
        rl.addSpacing(6)
        rl.addLayout(info)
        rl.addStretch()
        rl.addWidget(dur)
        rl.addSpacing(8)
        rl.addWidget(edit_hint)
    else:
        rl.addWidget(dot)
        rl.addSpacing(6)
        rl.addLayout(info)
        rl.addStretch()
        rl.addWidget(dur)
    return w

def _open_edit_session_dialog(parent: QWidget, dm: DataManager, session: dict, on_done):
    """Діалог редагування/видалення вже завершеного запису (категорія, дата, час початку, тривалість)."""
    # Активні категорії + (якщо сесія належить видаленій категорії) сама ця категорія,
    # щоб її можна було побачити в списку, не втративши прив'язку при збереженні.
    cats_for_combo = [
        c for c in dm.all_categories
        if not c.get("archived") or c["id"] == session["category_id"]
    ]
    if not cats_for_combo:
        return
    dlg = QDialog(parent)
    dlg.setWindowTitle("Редагувати запис")
    dlg.setStyleSheet(STYLE)
    dlg.setMinimumWidth(280)
    ll = QVBoxLayout(dlg)

    ll.addWidget(QLabel("Категорія:"))
    cat_combo = QComboBox()
    cur_idx = 0
    for i, cat in enumerate(cats_for_combo):
        cat_combo.addItem(cat["name"])
        if cat["id"] == session["category_id"]:
            cur_idx = i
    cat_combo.setCurrentIndex(cur_idx)
    ll.addWidget(cat_combo)

    start_dt = datetime.fromisoformat(session["start"])

    ll.addWidget(QLabel("Дата:"))
    date_edit = QDateEdit()
    date_edit.setCalendarPopup(True)
    date_edit.setDisplayFormat("dd.MM.yyyy")
    date_edit.setMaximumDate(QDate.currentDate())
    date_edit.setDate(QDate(start_dt.year, start_dt.month, start_dt.day))
    ll.addWidget(date_edit)

    ll.addWidget(QLabel("Час початку:"))
    time_edit = QTimeEdit()
    time_edit.setDisplayFormat("HH:mm")
    time_edit.setTime(QTime(start_dt.hour, start_dt.minute))
    ll.addWidget(time_edit)

    ll.addWidget(QLabel("Тривалість:"))
    hrs, mins, dur_row = _duration_spinboxes(session["duration"])
    ll.addLayout(dur_row)

    ll.addWidget(QLabel("Нотатка (необов'язково):"))
    note_edit = QLineEdit()
    note_edit.setPlaceholderText("напр. перерва на 30 хв")
    note_edit.setText(session.get("note", ""))
    ll.addWidget(note_edit)

    secondary_style = SECONDARY_BTN_STYLE

    prev_s, next_s = dm.find_adjacent_sessions(session["id"])

    merge_prev_btn = None
    if prev_s:
        p_start = datetime.fromisoformat(prev_s["start"]).strftime("%H:%M")
        p_end = datetime.fromisoformat(prev_s["end"]).strftime("%H:%M")
        merge_prev_btn = QPushButton(f"⤒ Об'єднати з попереднім ({p_start}–{p_end})")
        merge_prev_btn.setStyleSheet(secondary_style)

        def do_merge_prev():
            r = QMessageBox.question(
                dlg, "Об'єднати?", "Об'єднати цей запис із попереднім записом тієї ж категорії?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r == QMessageBox.StandardButton.Yes:
                dm.merge_sessions(prev_s["id"], session["id"])
                dlg.accept()
                on_done()

        merge_prev_btn.clicked.connect(do_merge_prev)

    merge_next_btn = None
    if next_s:
        n_start = datetime.fromisoformat(next_s["start"]).strftime("%H:%M")
        n_end = datetime.fromisoformat(next_s["end"]).strftime("%H:%M")
        merge_next_btn = QPushButton(f"⤓ Об'єднати з наступним ({n_start}–{n_end})")
        merge_next_btn.setStyleSheet(secondary_style)

        def do_merge_next():
            r = QMessageBox.question(
                dlg, "Об'єднати?", "Об'єднати цей запис із наступним записом тієї ж категорії?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if r == QMessageBox.StandardButton.Yes:
                dm.merge_sessions(session["id"], next_s["id"])
                dlg.accept()
                on_done()

        merge_next_btn.clicked.connect(do_merge_next)

    split_btn = None
    if session["duration"] >= 120:
        split_btn = QPushButton("✂ Розділити запис на дві частини")
        split_btn.setStyleSheet(secondary_style)

        def do_split():
            total_min = session["duration"] // 60
            sub = QDialog(dlg)
            sub.setWindowTitle("Розділити запис")
            sub.setStyleSheet(STYLE)
            sl = QVBoxLayout(sub)
            sl.addWidget(QLabel(f"Розділити після стільки хвилин від початку (всього {total_min} хв):"))
            split_spin = QSpinBox()
            split_spin.setRange(1, total_min - 1)
            split_spin.setValue(total_min // 2)
            split_spin.setSuffix(" хв")
            sl.addWidget(split_spin)
            confirm = QPushButton("Розділити")
            confirm.setObjectName("accentBtn")

            def do_confirm():
                dm.split_session(session["id"], split_spin.value() * 60)
                sub.accept()
                dlg.accept()
                on_done()

            confirm.clicked.connect(do_confirm)
            sl.addSpacing(4)
            sl.addWidget(confirm)
            sub.exec()

        split_btn.clicked.connect(do_split)

    save = QPushButton("Зберегти")
    save.setObjectName("accentBtn")

    def do_save():
        cat = cats_for_combo[cat_combo.currentIndex()]
        duration = hrs.value() * 3600 + mins.value() * 60
        if duration <= 0:
            QMessageBox.warning(dlg, "Помилка", "Тривалість має бути більшою за 0")
            return
        d = date_edit.date().toPyDate()
        t = time_edit.time().toPyTime()
        start = datetime.combine(d, t)
        dm.update_session(session["id"], cat["id"], start, duration, note_edit.text())
        dlg.accept()
        on_done()

    save.clicked.connect(do_save)

    delete_btn = QPushButton("Видалити запис")
    delete_btn.setStyleSheet(
        "QPushButton { background: #3A3A3C; color: #FF453A; border-radius: 8px; "
        "padding: 8px; font-size: 13px; }"
        "QPushButton:hover { background: #48484A; }"
    )

    def do_delete():
        r = QMessageBox.question(
            dlg, "Видалити?", "Видалити цей запис назавжди?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r == QMessageBox.StandardButton.Yes:
            dm.delete_session(session["id"])
            dlg.accept()
            on_done()

    delete_btn.clicked.connect(do_delete)

    ll.addSpacing(8)
    ll.addWidget(save)
    if merge_prev_btn:
        ll.addWidget(merge_prev_btn)
    if merge_next_btn:
        ll.addWidget(merge_next_btn)
    if split_btn:
        ll.addWidget(split_btn)
    ll.addWidget(delete_btn)
    dlg.exec()

def _open_edit_day_category_dialog(parent: QWidget, dm: DataManager, day: date, category_id: str,
                                     current_seconds: int, on_done):
    """Діалог зміни сумарного часу категорії за конкретний день."""
    cat = dm.get_category(category_id)
    dlg = QDialog(parent)
    dlg.setWindowTitle(cat["name"] if cat else "Категорія")
    dlg.setStyleSheet(STYLE)
    dlg.setMinimumWidth(280)
    ll = QVBoxLayout(dlg)

    info_lbl = QLabel(f"{cat['name'] if cat else category_id} — {format_date_ua(day)}")
    info_lbl.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 600;")
    ll.addWidget(info_lbl)

    ll.addWidget(QLabel("Загальний час за день:"))
    hrs, mins, dur_row = _duration_spinboxes(current_seconds)
    ll.addLayout(dur_row)

    save = QPushButton("Зберегти")
    save.setObjectName("accentBtn")

    def do_save():
        new_seconds = hrs.value() * 3600 + mins.value() * 60
        dm.set_day_category_duration(day.isoformat(), category_id, new_seconds)
        dlg.accept()
        on_done()

    save.clicked.connect(do_save)
    ll.addSpacing(8)
    ll.addWidget(save)
    dlg.exec()

def _open_edit_category_dialog(parent: QWidget, dm: DataManager, cat: dict, on_done):
    """Діалог редагування категорії: назва, колір, ціль."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Редагувати")
    dlg.setStyleSheet(STYLE)
    dlg.setMinimumWidth(280)
    ll = QVBoxLayout(dlg)
    name_edit = QLineEdit(cat["name"])
    new_color = [cat["color"]]
    color_btn = QPushButton("● Колір")
    color_btn.setStyleSheet(f"color: {cat['color']}; background: #2C2C2E; border-radius: 8px;")
    def pick():
        c = QColorDialog.getColor(QColor(cat["color"]), dlg)
        if c.isValid():
            new_color[0] = c.name()
            color_btn.setStyleSheet(f"color: {new_color[0]}; background: #2C2C2E; border-radius: 8px;")
    color_btn.clicked.connect(pick)

    goal_edit = QLineEdit()
    goal_edit.setPlaceholderText("напр. 60")
    if cat.get("goal_minutes"):
        goal_edit.setText(str(cat["goal_minutes"]))

    period_combo = QComboBox()
    period_options = [("day", "На день"), ("week", "На тиждень"), ("month", "На місяць")]
    for key, label in period_options:
        period_combo.addItem(label, key)
    cur_period = cat.get("goal_period", "day")
    idx = next((i for i, (k, _) in enumerate(period_options) if k == cur_period), 0)
    period_combo.setCurrentIndex(idx)

    save = QPushButton("Зберегти")
    save.setObjectName("accentBtn")
    def do_save():
        n = name_edit.text().strip()
        if n:
            cat["name"] = n
        cat["color"] = new_color[0]
        goal_text = goal_edit.text().strip()
        if goal_text:
            try:
                goal_val = int(goal_text)
                if goal_val > 0:
                    cat["goal_minutes"] = goal_val
                    cat["goal_period"] = period_combo.currentData()
                else:
                    cat.pop("goal_minutes", None)
                    cat.pop("goal_period", None)
            except ValueError:
                pass
        else:
            cat.pop("goal_minutes", None)
            cat.pop("goal_period", None)
        dm.save()
        dlg.accept()
        on_done()
    save.clicked.connect(do_save)
    ll.addWidget(QLabel("Назва:"))
    ll.addWidget(name_edit)
    ll.addWidget(color_btn)
    ll.addWidget(QLabel("Ціль, хв (необов'язково):"))
    ll.addWidget(goal_edit)
    ll.addWidget(period_combo)
    ll.addSpacing(8)
    ll.addWidget(save)

    ll.addSpacing(8)
    today_lbl = QLabel(f"Сьогоднішній час: {fmt_time(dm.get_today_time(cat['id']))}")
    today_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
    ll.addWidget(today_lbl)

    adj_row = QHBoxLayout()
    adj_spin = QSpinBox()
    adj_spin.setRange(-1440, 1440)
    adj_spin.setSingleStep(5)
    adj_spin.setSuffix(" хв")
    adj_spin.setValue(0)
    adj_row.addWidget(adj_spin, 1)
    apply_btn = QPushButton("Застосувати")
    apply_btn.setStyleSheet(SECONDARY_BTN_STYLE)

    def do_apply():
        delta = adj_spin.value() * 60
        if delta == 0:
            return
        today = date.today().isoformat()
        current = dm.get_today_time(cat["id"])
        new_total = max(0, current + delta)
        dm.set_day_category_duration(today, cat["id"], new_total)
        today_lbl.setText(f"Сьогоднішній час: {fmt_time(dm.get_today_time(cat['id']))}")
        adj_spin.setValue(0)
        on_done()

    apply_btn.clicked.connect(do_apply)
    adj_row.addWidget(apply_btn)
    ll.addWidget(QLabel("Додати/відняти хвилини сьогодні:"))
    ll.addLayout(adj_row)

    dlg.exec()
