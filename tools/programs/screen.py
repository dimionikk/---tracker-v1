import os

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QFileInfo
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QDialog, QLineEdit, QFileDialog, QFileIconProvider,
    QMenu, QInputDialog, QMessageBox, QApplication,
)

from .manager import ProgramsManager, launch_program, reveal_in_explorer

_ICON_PROVIDER = QFileIconProvider()


class _ScanWorker(QThread):
    done = pyqtSignal(int)

    def __init__(self, pm: ProgramsManager):
        super().__init__()
        self.pm = pm

    def run(self):
        added = 0
        com_ready = False
        try:
            import pythoncom
            pythoncom.CoInitialize()
            com_ready = True
        except Exception:
            pass
        try:
            added = self.pm.sync_scan()
        except Exception:
            added = 0
        finally:
            if com_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
        self.done.emit(added)


class AddProgramDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Додати програму")
        self.setMinimumWidth(420)

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Шлях до програми:"))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("Огляд…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        lay.addLayout(path_row)

        lay.addWidget(QLabel("Назва:"))
        self.name_edit = QLineEdit()
        lay.addWidget(self.name_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Скасувати")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        ok_btn = QPushButton("Додати")
        ok_btn.setObjectName("accentBtn")
        ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Виберіть програму", "", "Програми (*.exe);;Усі файли (*.*)"
        )
        if path:
            self.path_edit.setText(path)
            if not self.name_edit.text().strip():
                base = os.path.splitext(os.path.basename(path))[0]
                self.name_edit.setText(base)

    def _on_ok(self):
        if self.path_edit.text().strip() and self.name_edit.text().strip():
            self.accept()

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "path": self.path_edit.text().strip(),
        }


class IgnoreListDialog(QDialog):
    def __init__(self, pm: ProgramsManager, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.setWindowTitle("Ігнор-список")
        self.setMinimumSize(420, 320)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        self.empty_lbl = QLabel("Список порожній.")
        self.empty_lbl.setStyleSheet("color: #8E8E93; font-size: 13px;")
        root.addWidget(self.empty_lbl)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        self._scroll.setWidget(self._list_host)
        root.addWidget(self._scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._populate()

    def _populate(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ignored = self.pm.list_ignored()
        self.empty_lbl.setVisible(not ignored)
        self._scroll.setVisible(bool(ignored))

        for entry in ignored:
            row = QFrame()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(8, 6, 8, 6)
            name_lbl = QLabel(entry["name"])
            name_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
            row_lay.addWidget(name_lbl, 1)
            restore_btn = QPushButton("Повернути")
            restore_btn.clicked.connect(lambda _, p=entry["path"]: self._restore(p))
            row_lay.addWidget(restore_btn)
            self._list_lay.insertWidget(self._list_lay.count() - 1, row)

    def _restore(self, path: str):
        self.pm.unignore_item(path)
        self._populate()


class AvailableProgramsDialog(QDialog):
    def __init__(self, pm: ProgramsManager, parent=None):
        super().__init__(parent)
        self.pm = pm
        self.setWindowTitle("Усі програми")
        self.setMinimumSize(420, 320)

        root = QVBoxLayout(self)
        root.setSpacing(8)

        hint = QLabel("Знайдені програми, яких ще немає в основному списку.")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.empty_lbl = QLabel("Тут порожньо. Натисніть «🔄 Оновити», щоб пошукати програми.")
        self.empty_lbl.setStyleSheet("color: #8E8E93; font-size: 13px;")
        self.empty_lbl.setWordWrap(True)
        root.addWidget(self.empty_lbl)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._list_host = QWidget()
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        self._scroll.setWidget(self._list_host)
        root.addWidget(self._scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Закрити")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

        self._populate()

    def _populate(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        available = self.pm.list_available()
        self.empty_lbl.setVisible(not available)
        self._scroll.setVisible(bool(available))

        for entry in available:
            row = QFrame()
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(8, 6, 8, 6)
            name_lbl = QLabel(entry["name"])
            name_lbl.setStyleSheet("color: #FFFFFF; font-size: 13px;")
            row_lay.addWidget(name_lbl, 1)
            add_btn = QPushButton("+ Додати")
            add_btn.setObjectName("accentBtn")
            add_btn.clicked.connect(lambda _, p=entry["path"]: self._activate(p))
            row_lay.addWidget(add_btn)
            self._list_lay.insertWidget(self._list_lay.count() - 1, row)

    def _activate(self, path: str):
        self.pm.activate_item(path)
        self._populate()


class ProgramTile(QFrame):
    SIZE = (240, 34)

    def __init__(self, item, on_launch, on_ignore, on_pin, on_rename, parent=None):
        super().__init__(parent)
        self.item_id = item["id"]
        self._item = item
        self._on_launch = on_launch
        self._on_rename = on_rename

        self.setFixedSize(*self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QFrame { background: #2C2C2E; border-radius: 8px; }"
            "QFrame:hover { background: #3A3A3C; }"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 3, 3)
        lay.setSpacing(6)

        icon_lbl = QLabel()
        icon_lbl.setFixedSize(20, 20)
        icon_lbl.setStyleSheet("background: transparent;")
        icon = _ICON_PROVIDER.icon(QFileInfo(item["path"]))
        icon_lbl.setPixmap(icon.pixmap(20, 20))
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        valid = os.path.exists(item["path"])

        name_lbl = QLabel(item["name"])
        if valid:
            name_lbl.setStyleSheet("color: #FFFFFF; font-size: 9px; font-weight: 600;")
        else:
            name_lbl.setStyleSheet("color: #8E8E93; font-size: 9px; font-weight: 600;")
            name_lbl.setToolTip(f'Файл не знайдено: {item["path"]}')
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        if not valid:
            warn_lbl = QLabel("⚠")
            warn_lbl.setStyleSheet("color: #FF9F0A; font-size: 12px; background: transparent;")
            warn_lbl.setToolTip(f'Файл не знайдено: {item["path"]}')
            lay.addWidget(warn_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        pinned = item.get("pinned", False)
        pin_btn = QPushButton("📌")
        pin_btn.setFixedSize(22, 22)
        if pinned:
            pin_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #FFD60A;"
                " border: none; border-radius: 6px; font-size: 13px; padding: 0px; }"
                "QPushButton:hover { background: #4A4A2A; }"
            )
            pin_btn.setToolTip("Відкріпити")
        else:
            pin_btn.setStyleSheet(
                "QPushButton { background: transparent; color: #8E8E93;"
                " border: none; border-radius: 6px; font-size: 13px; padding: 0px; }"
                "QPushButton:hover { background: #4A4A2A; color: #FFD60A; }"
            )
            pin_btn.setToolTip("Закріпити зверху")
        pin_btn.clicked.connect(lambda: on_pin(item["id"]))
        lay.addWidget(pin_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        ignore_btn = QPushButton("✕")
        ignore_btn.setFixedSize(22, 22)
        ignore_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #FF453A;"
            " border: none; border-radius: 6px; font-size: 14px; padding: 0px; }"
            "QPushButton:hover { background: #4A2A2A; }"
        )
        ignore_btn.setToolTip("Прибрати зі списку (більше не пропонувати)")
        ignore_btn.clicked.connect(lambda: on_ignore(item["id"]))
        lay.addWidget(ignore_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_launch(self.item_id)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        open_action = menu.addAction("Відкрити розташування файлу")
        copy_action = menu.addAction("Копіювати шлях")
        rename_action = menu.addAction("Перейменувати")
        action = menu.exec(event.globalPos())
        if action == open_action:
            reveal_in_explorer(self._item["path"])
        elif action == copy_action:
            QApplication.clipboard().setText(self._item["path"])
        elif action == rename_action:
            self._on_rename(self.item_id, self._item["name"])


class ProgramsScreen(QWidget):
    SPACING = 10

    def __init__(self, pm: ProgramsManager, parent=None):
        super().__init__(parent)
        self.pm = pm
        self._tiles = {}
        self._cols = 0
        self._scan_thread = None
        self._separator = None
        self._pinned_count = 0

        self._setup_ui()
        self.refresh()
        self._on_scan(silent=True)

    # ------------------------------------------------------------------ #
    # UI
    # ------------------------------------------------------------------ #
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Програми")
        title.setStyleSheet("color: #FFFFFF; font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        add_btn = QPushButton("+ Додати")
        add_btn.setObjectName("accentBtn")
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)

        ignore_btn = QPushButton("🚫 Ігнор-список")
        ignore_btn.clicked.connect(self._on_ignore_list)
        header.addWidget(ignore_btn)

        available_btn = QPushButton("📋 Усі програми")
        available_btn.clicked.connect(self._on_available_list)
        header.addWidget(available_btn)

        self._scan_btn = QPushButton("🔄 Оновити")
        self._scan_btn.clicked.connect(lambda: self._on_scan(silent=False))
        header.addWidget(self._scan_btn)

        clear_btn = QPushButton("🗑 Очистити список")
        clear_btn.clicked.connect(self._on_clear_all)
        header.addWidget(clear_btn)

        root.addLayout(header)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
        self.status_lbl.hide()
        root.addWidget(self.status_lbl)

        self.empty_lbl = QLabel(
            "Тут ще немає програм. Натисніть «🔄 Оновити», щоб знайти "
            "встановлені програми."
        )
        self.empty_lbl.setStyleSheet("color: #8E8E93; font-size: 13px;")
        self.empty_lbl.setWordWrap(True)
        self.empty_lbl.hide()
        root.addWidget(self.empty_lbl)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setSpacing(self.SPACING)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_host)

        root.addWidget(self._scroll, 1)

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #
    def refresh(self):
        self.setUpdatesEnabled(False)
        try:
            for tile in self._tiles.values():
                tile.deleteLater()
            self._tiles = {}

            items = self.pm.list_items()
            self._pinned_count = sum(1 for i in items if i.get("pinned"))

            for item in items:
                tile = ProgramTile(item, self._launch, self._ignore, self._pin, self._rename)
                self._tiles[item["id"]] = tile

            self._cols = 0
            self._relayout(force=True)
        finally:
            self.setUpdatesEnabled(True)

    def _get_separator(self) -> QFrame:
        if self._separator is None:
            self._separator = QFrame()
            self._separator.setFixedSize(ProgramTile.SIZE[0], 2)
            self._separator.setStyleSheet("background: #48484A; border-radius: 1px;")
        return self._separator

    def _relayout(self, force: bool = False):
        if self._cols == 1 and not force:
            return
        self._cols = 1

        for i in reversed(range(self._grid.count())):
            self._grid.takeAt(i)

        tiles = list(self._tiles.values())
        show_separator = 0 < self._pinned_count < len(tiles)

        row = 0
        for idx, tile in enumerate(tiles):
            if show_separator and idx == self._pinned_count:
                self._grid.addWidget(self._get_separator(), row, 0)
                row += 1
            self._grid.addWidget(tile, row, 0)
            row += 1

        if self._separator is not None:
            self._separator.setVisible(show_separator)

        if tiles:
            self.empty_lbl.hide()
        else:
            self.empty_lbl.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #
    def _launch(self, item_id: str):
        item = self.pm.get_item(item_id)
        if not item:
            return
        ok, err = launch_program(item["path"])
        if not ok:
            self.status_lbl.setStyleSheet("color: #FF453A; font-size: 12px;")
            self.status_lbl.setText(f'Не вдалося запустити "{item["name"]}": {err}')
            self.status_lbl.show()

    def _ignore(self, item_id: str):
        self.pm.ignore_item(item_id)
        self.refresh()

    def _pin(self, item_id: str):
        self.pm.toggle_pin(item_id)
        self.refresh()

    def _rename(self, item_id: str, current_name: str):
        new_name, ok = QInputDialog.getText(
            self, "Перейменувати", "Назва програми:", text=current_name
        )
        if ok and new_name.strip():
            self.pm.rename_item(item_id, new_name.strip())
            self.refresh()

    def _on_clear_all(self):
        if not self.pm.list_items():
            return
        reply = QMessageBox.question(
            self,
            "Очистити список",
            "Видалити всі програми зі списку? Цю дію неможливо скасувати.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.pm.clear_items()
            self.refresh()

    def _on_add(self):
        dlg = AddProgramDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self.pm.add_item(data["name"], data["path"])
            self.refresh()

    def _on_ignore_list(self):
        dlg = IgnoreListDialog(self.pm, self)
        dlg.exec()
        self.refresh()

    def _on_available_list(self):
        dlg = AvailableProgramsDialog(self.pm, self)
        dlg.exec()
        self.refresh()

    # ------------------------------------------------------------------ #
    # Сканування
    # ------------------------------------------------------------------ #
    def _on_scan(self, silent: bool = False):
        if self._scan_thread is not None:
            return
        if not silent:
            self.status_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
            self.status_lbl.setText("Шукаємо програми в меню «Пуск»…")
            self.status_lbl.show()
        self._scan_btn.setEnabled(False)

        self._scan_thread = _ScanWorker(self.pm)
        self._scan_thread.done.connect(lambda added: self._on_scan_done(added, silent))
        self._scan_thread.start()

    def _on_scan_done(self, added: int, silent: bool):
        self._scan_thread = None
        self._scan_btn.setEnabled(True)

        if added:
            self.status_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
            self.status_lbl.setText(
                f"Знайдено нових програм: {added} (дивіться «📋 Усі програми»)"
            )
            self.status_lbl.show()
        elif not silent:
            self.status_lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
            self.status_lbl.setText("Нових програм не знайдено")
            self.status_lbl.show()
        elif not self._tiles:
            self.status_lbl.hide()
