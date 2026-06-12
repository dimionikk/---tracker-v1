import os
import sys
from datetime import date, timedelta
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QPushButton

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

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

def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}г {m:02d}хв {s:02d}с"

def fmt_timer(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()

def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
    return lbl

def icon_btn(icon: str, callback, data, danger: bool = False) -> QPushButton:
    btn = QPushButton(icon)
    btn.setFixedSize(28, 28)
    color = "#FF453A" if danger else "#FFFFFF"
    btn.setStyleSheet(
        f"QPushButton {{ background: #3A3A3C; border-radius: 6px; color: {color}; "
        f"font-size: 14px; padding: 0px; }}"
        f"QPushButton:hover {{ background: #48484A; }}"
    )
    btn.clicked.connect(lambda: callback(data))
    return btn

_AUTOSTART_NAME = "MoiInstrumenty"

def _autostart_command() -> str:
    vbs = PROJECT_ROOT / "start.vbs"
    wscript = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe"
    return f'"{wscript}" "{vbs}"'

def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, _AUTOSTART_NAME)
            return True
    except OSError:
        return False

def set_autostart(enabled: bool):
    if sys.platform != "win32":
        return
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, _AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
