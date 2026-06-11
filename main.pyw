import sys, importlib.util, subprocess as _sp, os as _os

_DEPS = [
    ("PyQt6",    "PyQt6"),
    ("psutil",   "psutil"),
    ("win32gui", "pywin32"),
]
_missing = [pkg for mod, pkg in _DEPS if importlib.util.find_spec(mod) is None]

if _missing:
    try:
        import tkinter as _tk
        from tkinter import ttk as _ttk
        _root = _tk.Tk()
        _root.title("Інструменти — встановлення")
        _root.geometry("340x90")
        _root.resizable(False, False)
        _root.eval("tk::PlaceWindow . center")
        _tk.Label(
            _root,
            text=f"Встановлення залежностей: {', '.join(_missing)}",
            font=("Arial", 10),
        ).pack(pady=(12, 4))
        _bar = _ttk.Progressbar(_root, mode="indeterminate", length=280)
        _bar.pack()
        _bar.start(12)
        _root.update()
        _sp.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *_missing],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
        _root.destroy()
    except Exception:
        _sp.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *_missing],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
    _os.execv(sys.executable, [sys.executable] + sys.argv)

import os
import socket
import traceback
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QButtonGroup, QSystemTrayIcon, QMenu
)
from PyQt6.QtGui import QIcon

from styles import STYLE
from tools.logger import log
from tools.notifications import SettingsManager
from tools.tracker import TrackerTool
from tools.planner import PlannerTool
from tools.settings import SettingsTool

def _log_uncaught(exc_type, exc_value, exc_tb):
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log("ERROR", f"Необроблена помилка:\n{text}")

sys.excepthook = _log_uncaught

_settings_manager = SettingsManager()

TOOLS = [
    TrackerTool(),
    PlannerTool(_settings_manager),
    SettingsTool(_settings_manager),
]

class Sidebar(QWidget):
    def __init__(self, tools: list, on_select):
        super().__init__()
        self.setObjectName("sidebar")
        self.setFixedWidth(72)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 14, 6, 14)
        lay.setSpacing(6)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for i, tool in enumerate(tools):
            btn = QPushButton(f"{tool.ICON}\n{tool.TITLE}")
            btn.setObjectName("sidebarBtn")
            btn.setCheckable(True)
            btn.setFixedHeight(56)
            btn.clicked.connect(lambda _, idx=i: on_select(idx))
            self._group.addButton(btn, i)
            lay.addWidget(btn)

        lay.addStretch()
        self._group.button(0).setChecked(True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мої інструменти")
        self.setMinimumSize(780, 620)
        self.resize(864, 720)
        self.setStyleSheet(STYLE)
        self._setup_ui()
        self._setup_tray()
        for tool in TOOLS:
            tool.set_notify(self._notify)

    def _notify(self, title: str, message: str):
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = Sidebar(TOOLS, self._switch_tool)
        root.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        for tool in TOOLS:
            self._stack.addWidget(tool.build_widget())
        root.addWidget(self._stack, 1)

        TOOLS[0].on_activate()

    def _switch_tool(self, idx: int):
        if idx == self._stack.currentIndex():
            return
        TOOLS[self._stack.currentIndex()].on_deactivate()
        self._stack.setCurrentIndex(idx)
        TOOLS[idx].on_activate()
        log("APP", f"Перемкнено інструмент: {TOOLS[idx].TITLE}")

    def _setup_tray(self):
        icon_path = Path(os.path.dirname(os.path.abspath(__file__))) / "icon.ico"
        app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        self.setWindowIcon(app_icon)
        self._tray = QSystemTrayIcon(app_icon, self)
        self._tray.setToolTip("Мої інструменти")
        menu = QMenu()
        menu.addAction("Відкрити", self._show_from_tray)
        menu.addAction("Вийти", self._quit_app)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(
            lambda r: self._show_from_tray() if r == QSystemTrayIcon.ActivationReason.Trigger else None
        )
        self._tray.show()

    def _show_from_tray(self):
        log("APP", "Вікно відкрито з трею")
        self.show()

    def _quit_app(self):
        log("APP", "Вихід з програми (через трей)")
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        log("APP", "Вікно згорнуто у трей")
        self._tray.showMessage(
            "Мої інструменти", "Згорнуто в трей. ПКМ по іконці -> Вийти.",
            QSystemTrayIcon.MessageIcon.Information, 2500
        )

_lock_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _lock_sock.bind(('127.0.0.1', 47291))
except OSError:
    log("APP", "Повторний запуск заблоковано — програма вже запущена")
    sys.exit(0)

def main():
    log("APP", "Програма запущена")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Tracker")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
