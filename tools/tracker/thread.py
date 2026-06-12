import sys
import time
import subprocess

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

def get_idle_seconds() -> float:
    """Кількість секунд без активності користувача (миша/клавіатура). 0, якщо невідомо."""
    if sys.platform != "win32":
        return 0.0
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
        return max(0.0, millis / 1000.0)
    except Exception:
        return 0.0

class WindowTrackerThread(QThread):
    window_changed = pyqtSignal(str, str)
    idle_changed = pyqtSignal(bool)

    def __init__(self, dm=None):
        super().__init__()
        self.dm = dm
        self._running = True
        self._last_process = ""
        self._last_title = ""
        self._was_idle = False

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
            title = title or ""
            if proc and (proc != self._last_process or title != self._last_title):
                self._last_process = proc
                self._last_title = title
                self.window_changed.emit(proc, title)

            if self.dm is not None and self.dm.settings.get("idle_detection", True):
                threshold_min = self.dm.settings.get("idle_threshold_min", 5)
                idle = get_idle_seconds() >= threshold_min * 60
            else:
                idle = False
            if idle != self._was_idle:
                self._was_idle = idle
                self.idle_changed.emit(idle)

            time.sleep(3)

    def stop(self):
        self._running = False
