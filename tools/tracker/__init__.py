from PyQt6.QtWidgets import QApplication

from tools.base import BaseTool
from tools.logger import log
from .manager import DataManager
from .thread import WindowTrackerThread
from .screen import TrackerScreen

class TrackerTool(BaseTool):
    TITLE = "Трекер"
    ICON = "⏱"

    def __init__(self):
        self.dm = DataManager()
        self._screen: TrackerScreen | None = None
        self._wt: WindowTrackerThread | None = None

    def build_widget(self):
        self._screen = TrackerScreen(self.dm)
        self._start_window_tracker()
        return self._screen

    def _start_window_tracker(self):
        self._wt = WindowTrackerThread()
        self._wt.window_changed.connect(self._on_window)
        self._wt.start()
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def _on_window(self, proc: str, _title: str):
        log("AUTO", f"Активне вікно змінилося: {proc}")
        cat_id = self.dm.get_category_for_process(proc)
        if cat_id:
            self._screen.auto_start(cat_id)
        else:
            self._screen.auto_stop()

    def shutdown(self):
        if self._wt:
            log("AUTO", "Зупинка авто-трекера активних вікон")
            self._wt.stop()
            self._wt.wait(2000)
