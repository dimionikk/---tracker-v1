from datetime import date, datetime, timedelta

import psutil
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QScrollArea, QFrame, QStackedWidget, QCheckBox, QLineEdit,
    QDialog, QListWidget, QMessageBox, QColorDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter

from styles import STYLE, CATEGORY_COLORS
from tools.common import (
    fmt_time, fmt_timer, clear_layout, section_label, icon_btn,
    is_autostart_enabled, set_autostart, format_date_ua,
)
from .manager import DataManager

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
    def __init__(self, category: dict, seconds: int, active: bool = False):
        super().__init__()
        self.setFixedHeight(68)
        border = category["color"] if active else "#3A3A3C"
        self.setStyleSheet(
            f"QFrame {{ background: #2C2C2E; border-radius: 12px; border: 1.5px solid {border}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
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
        time_lbl.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: 500; border: none;")
        lay.addWidget(time_lbl)

class TrackerScreen(QWidget):
    def __init__(self, dm: DataManager, on_global_refresh=None):
        super().__init__()
        self.dm = dm
        self._on_global_refresh = on_global_refresh
        self._auto_active = False
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

        timer_frame = QFrame()
        timer_frame.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 14px; }")
        timer_frame.setMinimumHeight(110)
        tl = QVBoxLayout(timer_frame)
        tl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tl.setSpacing(6)

        self._timer_status = QLabel("Оберіть категорію і натисни ▶")
        self._timer_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_status.setStyleSheet("color: #8E8E93; font-size: 13px;")

        self._timer_display = QLabel("00:00:00")
        self._timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer_display.setStyleSheet(
            "color: #FFFFFF; font-size: 36px; font-weight: 300; font-family: 'Courier New', monospace;"
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

        lay.addWidget(section_label("ПРОГРАМИ"))
        self._auto_map_widget = QWidget()
        self._auto_map_layout = QVBoxLayout(self._auto_map_widget)
        self._auto_map_layout.setContentsMargins(0, 0, 0, 0)
        self._auto_map_layout.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidget(self._auto_map_widget)
        scroll.setWidgetResizable(True)
        lay.addWidget(scroll)

        lay.addWidget(section_label("ДОДАТИ"))
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
        clear_layout(self._auto_map_layout)
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
        prev_idx = self._combo.currentIndex()
        self._combo.clear()
        self._combo.addItem("Оберіть категорію…")
        for c in self.dm.categories:
            self._combo.addItem(c["name"])
        if 0 < prev_idx <= len(self.dm.categories):
            self._combo.setCurrentIndex(prev_idx)

        clear_layout(self._cards_grid)
        active_cid = self.dm.active_session["category_id"] if self.dm.active_session else None
        for i, cat in enumerate(self.dm.categories):
            card = CategoryCard(cat, self.dm.get_today_time(cat["id"]), cat["id"] == active_cid)
            self._cards_grid.addWidget(card, i // 2, i % 2)

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

        clear_layout(self._journal_layout)
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
            if secs % 60 == 0:
                clear_layout(self._cards_grid)
                active_cid = self.dm.active_session["category_id"]
                for i, cat in enumerate(self.dm.categories):
                    card = CategoryCard(cat, self.dm.get_today_time(cat["id"]), cat["id"] == active_cid)
                    self._cards_grid.addWidget(card, i // 2, i % 2)

    def _on_start(self):
        idx = self._combo.currentIndex()
        if idx <= 0:
            return
        cat = self.dm.categories[idx - 1]
        self._auto_active = False
        self.dm.start_session(cat["id"])
        self.refresh()

    def _on_stop(self):
        self._auto_active = False
        self.dm.stop_session()
        self.refresh()

    def auto_start(self, category_id: str):
        if self.dm.active_session and self.dm.active_session["category_id"] == category_id:
            return
        if self.dm.active_session and not self._auto_active:
            return
        self._auto_active = True
        self.dm.start_session(category_id)
        self.refresh()

    def auto_stop(self):
        if self.dm.active_session and self._auto_active:
            self._auto_active = False
            self.dm.stop_session()
            self.refresh()

class StatisticsScreen(QWidget):
    def __init__(self, dm: DataManager):
        super().__init__()
        self.dm = dm
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
        for key, label in [("day", "День"), ("week", "Тиждень"), ("month", "Місяць")]:
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

    def refresh(self):
        self._day_nav.setVisible(self._period == "day")
        if self._period == "day":
            self._day_lbl.setText(format_date_ua(self._day))
            stats = self.dm.get_day_stats(self._day.isoformat())
        else:
            stats = self.dm.get_period_stats(self._period)
        total = sum(stats.values())
        self._total_big.setText(fmt_time(total))

        top_id = max(stats, key=stats.get) if any(stats.values()) else None
        if top_id:
            cat = self.dm.get_category(top_id)
            self._top_big.setText(cat["name"] if cat else "—")
        else:
            self._top_big.setText("—")

        clear_layout(self._bars_layout)
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

        lay.addWidget(section_label("ЗАГАЛЬНЕ"))
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
        clear_layout(self._cat_ll)
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
        edit_btn = icon_btn("✎", self._edit_category, cat)
        del_btn  = icon_btn("✕", self._delete_category, cat, danger=True)
        rl.addWidget(dot)
        rl.addWidget(name)
        rl.addStretch()
        rl.addWidget(edit_btn)
        rl.addWidget(del_btn)
        return w

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
