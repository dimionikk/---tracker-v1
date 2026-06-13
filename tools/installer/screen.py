from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QTextEdit, QLineEdit,
)

from tools.common import section_label
from .manager import ConsoleProcess, install_command, load_catalog


class CatalogTile(QFrame):
    """Один рядок каталогу winget-програм із кнопкою «Встановити»."""

    def __init__(self, entry: dict, on_install, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setFixedHeight(38)
        self.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 8px; }")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 6, 4)
        lay.setSpacing(8)

        name_lbl = QLabel(entry["name"])
        name_lbl.setStyleSheet("color: #FFFFFF; font-size: 12px; font-weight: 600;")
        name_lbl.setWordWrap(True)
        lay.addWidget(name_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        install_btn = QPushButton("Встановити")
        install_btn.setObjectName("accentBtn")
        install_btn.setFixedHeight(26)
        install_btn.clicked.connect(lambda: on_install(entry))
        lay.addWidget(install_btn, 0, Qt.AlignmentFlag.AlignVCenter)


class InstallerScreen(QWidget):
    """Розділ «Встановлення»: консоль із правами адміністратора +
    каталог популярних програм для встановлення через winget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._console = ConsoleProcess(self)
        self._console.output_received.connect(self._append_output)
        self._console.finished.connect(self._on_console_finished)
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Встановлення")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        admin_lbl = QLabel("🛡 Запущено від імені адміністратора")
        admin_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        header.addWidget(admin_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(16)
        root.addLayout(body, 1)

        body.addLayout(self._build_catalog_column(), 0)
        body.addLayout(self._build_console_column(), 1)

    def _build_catalog_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        col.addWidget(section_label("КАТАЛОГ ПРОГРАМ (WINGET)"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(264)
        col.addWidget(scroll, 1)

        catalog_widget = QWidget()
        catalog_lay = QVBoxLayout(catalog_widget)
        catalog_lay.setContentsMargins(0, 0, 8, 0)
        catalog_lay.setSpacing(6)

        for entry in load_catalog():
            catalog_lay.addWidget(CatalogTile(entry, self._install))
        catalog_lay.addStretch()

        scroll.setWidget(catalog_widget)
        return col

    def _build_console_column(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(8)

        col.addWidget(section_label("КОНСОЛЬ"))

        self._output = QTextEdit()
        self._output.setObjectName("consoleOutput")
        self._output.setReadOnly(True)
        col.addWidget(self._output, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QLineEdit()
        self._input.setObjectName("consoleInput")
        self._input.setPlaceholderText("Введіть команду і натисніть Enter…")
        self._input.returnPressed.connect(self._run_command)
        input_row.addWidget(self._input, 1)

        run_btn = QPushButton("Виконати")
        run_btn.setObjectName("accentBtn")
        run_btn.clicked.connect(self._run_command)
        input_row.addWidget(run_btn)

        clear_btn = QPushButton("Очистити")
        clear_btn.clicked.connect(self._output.clear)
        input_row.addWidget(clear_btn)

        col.addLayout(input_row)
        return col

    # ------------------------------------------------------------------
    def _install(self, entry: dict):
        cmd = install_command(entry["id"])
        self._append_output(f"\n> {cmd}\n")
        self._console.write_command(cmd)

    def _run_command(self):
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._append_output(f"\n> {cmd}\n")
        self._console.write_command(cmd)
        self._input.clear()

    def _append_output(self, text: str):
        self._output.moveCursor(QTextCursor.MoveOperation.End)
        self._output.insertPlainText(text)
        self._output.moveCursor(QTextCursor.MoveOperation.End)

    def _on_console_finished(self, _exit_code):
        self._append_output("\n[Консоль завершила роботу.]\n")

    def shutdown(self):
        self._console.stop()
