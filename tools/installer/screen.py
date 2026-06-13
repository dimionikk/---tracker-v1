from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QCheckBox, QButtonGroup,
)

from tools.common import section_label
from .manager import (
    batch_install_command, batch_uninstall_command, group_by_category,
    get_installed_ids, install_command, load_catalog, open_console,
    uninstall_command, upgrade_all_command,
)


class _InstalledScanner(QThread):
    """Фоновий потік: визначає, які програми каталогу вже встановлені
    (через `winget export`), щоб не блокувати інтерфейс."""

    finished_scan = pyqtSignal(set)

    def run(self):
        self.finished_scan.emit(get_installed_ids())


class CatalogTile(QFrame):
    """Один рядок каталогу winget-програми.

    mode="install": кнопка «Встановити» (або «Встановлено», якщо програма
    вже є в системі — без чекбоксу, нічого встановлювати). mode="uninstall":
    кнопка «Видалити». Якщо передано on_toggle — додається чекбокс для
    позначення програми для масової дії."""

    def __init__(self, entry: dict, on_action, parent=None,
                 installed=False, mode="install", on_toggle=None):
        super().__init__(parent)
        self.entry = entry
        self.setMinimumHeight(40)
        self.setStyleSheet("QFrame { background: #3A3A3C; border-radius: 8px; }")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(10)

        if on_toggle is not None:
            check = QCheckBox()
            check.setObjectName("selectCheck")
            check.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            check.setToolTip("Позначити для масової дії")
            check.toggled.connect(lambda checked: on_toggle(entry, checked))
            lay.addWidget(check, 0, Qt.AlignmentFlag.AlignVCenter)

        name_lbl = QLabel(entry["name"])
        name_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 600;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl, 1)

        if mode == "uninstall":
            action_btn = QPushButton("Видалити")
            action_btn.setObjectName("stopBtn")
            action_btn.clicked.connect(lambda: on_action(entry))
        elif installed:
            action_btn = QPushButton("Встановлено")
            action_btn.setEnabled(False)
        else:
            action_btn = QPushButton("Встановити")
            action_btn.setObjectName("accentBtn")
            action_btn.clicked.connect(lambda: on_action(entry))
        action_btn.setFixedHeight(28)
        action_btn.setMinimumWidth(100)
        lay.addWidget(action_btn, 0, Qt.AlignmentFlag.AlignVCenter)


class CategoryHeader(QLabel):
    """Заголовок категорії програм у спільному списку."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "color: #FFFFFF; font-size: 14px; font-weight: 700; "
            "padding-top: 6px;"
        )


class CategorySeparator(QFrame):
    """Горизонтальна риска між категоріями."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet("background-color: #3A3A3C; border: none;")


class InstallerScreen(QWidget):
    """Розділ «Встановлення»: перемикач режиму Встановити/Видалити, кнопки
    «Оновити все» та «Консоль», пошук програм і єдиний список каталогу
    winget-програм — категорії та їх програми прописані прямо у вікні,
    розділені горизонтальними рисками, з масовим встановленням/видаленням
    обраних."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "install"
        self._installed_ids: set[str] | None = None
        self._selected: dict[str, dict] = {}
        self._setup_ui()
        self._start_scan()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Встановлення")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self._mode_install_btn = QPushButton("Встановити")
        self._mode_install_btn.setObjectName("modeBtn")
        self._mode_install_btn.setCheckable(True)
        self._mode_install_btn.setChecked(True)

        self._mode_uninstall_btn = QPushButton("Видалити")
        self._mode_uninstall_btn.setObjectName("modeBtn")
        self._mode_uninstall_btn.setCheckable(True)

        self._mode_group = QButtonGroup(self)
        self._mode_group.setExclusive(True)
        self._mode_group.addButton(self._mode_install_btn)
        self._mode_group.addButton(self._mode_uninstall_btn)
        self._mode_group.buttonToggled.connect(self._on_mode_toggled)

        header.addWidget(self._mode_install_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._mode_uninstall_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        update_btn = QPushButton("Оновити все")
        update_btn.setObjectName("accentBtn")
        update_btn.clicked.connect(lambda: open_console(upgrade_all_command()))
        header.addWidget(update_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        console_btn = QPushButton("Консоль")
        console_btn.setObjectName("accentBtn")
        console_btn.clicked.connect(lambda: open_console())
        header.addWidget(console_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Пошук програми...")
        self._search.textChanged.connect(self._on_search)
        root.addWidget(self._search)

        self._section_lbl = section_label("КАТЕГОРІЇ ПРОГРАМ (WINGET)")
        root.addWidget(self._section_lbl)

        self._catalog = load_catalog()
        self._groups = group_by_category(self._catalog)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._build_list())
        root.addWidget(self._scroll, 1)

        self._batch_btn = QPushButton("Встановити обрані")
        self._batch_btn.setObjectName("accentBtn")
        self._batch_btn.setEnabled(False)
        self._batch_btn.clicked.connect(self._run_batch)
        root.addWidget(self._batch_btn)

    # ------------------------------------------------------------------
    def _start_scan(self):
        self._scanner = _InstalledScanner(self)
        self._scanner.finished_scan.connect(self._on_scanned)
        self._scanner.start()

    def _on_scanned(self, ids: set):
        self._installed_ids = ids
        self._selected.clear()
        self._scroll.setWidget(self._build_list())
        self._update_batch_btn()

    # ------------------------------------------------------------------
    def _filtered_groups(self, query: str) -> dict[str, list[dict]]:
        if not query:
            return self._groups
        result: dict[str, list[dict]] = {}
        for category, entries in self._groups.items():
            matched = [e for e in entries if query in e["name"].lower()]
            if matched:
                result[category] = matched
        return result

    def _build_list(self) -> QWidget:
        if self._mode == "uninstall" and self._installed_ids is None:
            return self._loading_widget("Перевірка встановлених програм...")

        query = self._search.text().strip().lower()
        groups = self._filtered_groups(query)
        installed_ids = self._installed_ids or set()

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 8, 0)
        lay.setSpacing(6)

        any_shown = False
        first = True
        for category, entries in groups.items():
            if self._mode == "uninstall":
                entries = [e for e in entries if e["id"] in installed_ids]
            if not entries:
                continue

            if not first:
                lay.addWidget(CategorySeparator())
            first = False
            any_shown = True

            lay.addWidget(CategoryHeader(category))

            for entry in entries:
                installed = entry["id"] in installed_ids
                on_toggle = (self._toggle
                              if (self._mode == "uninstall" or not installed) else None)
                tile = CatalogTile(
                    entry, self._action,
                    installed=installed, mode=self._mode, on_toggle=on_toggle,
                )
                lay.addWidget(tile)

        if not any_shown:
            if self._mode == "uninstall":
                msg = "Немає встановлених програм"
            elif query:
                msg = "Нічого не знайдено"
            else:
                msg = "Каталог порожній"
            empty = QLabel(msg)
            empty.setStyleSheet("color: #8E8E93; font-size: 12px;")
            lay.addWidget(empty)

        lay.addStretch()
        return container

    @staticmethod
    def _loading_widget(text: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    # ------------------------------------------------------------------
    def _on_mode_toggled(self, _button, _checked):
        self._mode = "install" if self._mode_install_btn.isChecked() else "uninstall"
        self._selected.clear()
        self._scroll.setWidget(self._build_list())
        self._update_batch_btn()

    # ------------------------------------------------------------------
    def _on_search(self, text: str):
        query = text.strip().lower()
        self._section_lbl.setText("РЕЗУЛЬТАТИ ПОШУКУ" if query else "КАТЕГОРІЇ ПРОГРАМ (WINGET)")
        self._selected.clear()
        self._scroll.setWidget(self._build_list())
        self._update_batch_btn()

    # ------------------------------------------------------------------
    def _toggle(self, entry: dict, checked: bool):
        if checked:
            self._selected[entry["id"]] = entry
        else:
            self._selected.pop(entry["id"], None)
        self._update_batch_btn()

    def _update_batch_btn(self):
        verb = "Встановити" if self._mode == "install" else "Видалити"
        n = len(self._selected)
        self._batch_btn.setText(f"{verb} обрані ({n})" if n else f"{verb} обрані")
        self._batch_btn.setEnabled(n > 0)

        obj_name = "accentBtn" if self._mode == "install" else "stopBtn"
        if self._batch_btn.objectName() != obj_name:
            self._batch_btn.setObjectName(obj_name)
            self._batch_btn.style().unpolish(self._batch_btn)
            self._batch_btn.style().polish(self._batch_btn)

    def _run_batch(self):
        ids = [e["id"] for e in self._selected.values()]
        if not ids:
            return
        if self._mode == "uninstall":
            open_console(batch_uninstall_command(ids))
        else:
            open_console(batch_install_command(ids))
        self._selected.clear()
        self._scroll.setWidget(self._build_list())
        self._update_batch_btn()

    # ------------------------------------------------------------------
    def _action(self, entry: dict):
        if self._mode == "uninstall":
            open_console(uninstall_command(entry["id"]))
        else:
            open_console(install_command(entry["id"]))
