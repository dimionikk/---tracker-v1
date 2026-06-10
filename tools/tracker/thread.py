import sys
import time
import subprocess

import psutil
from PyQt6.QtCore import QThread, pyqtSignal

class WindowTrackerThread(QThread):
    window_changed = pyqtSignal(str, str)

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
