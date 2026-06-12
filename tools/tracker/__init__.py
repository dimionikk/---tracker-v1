from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from tools.base import BaseTool
from .manager import DataManager, UNCATEGORIZED_ID
from .thread import WindowTrackerThread
from .screen import TrackerScreen

REMINDER_CHECK_MS = 60_000

class TrackerTool(BaseTool):
    TITLE = "Трекер"
    ICON = "⏱"

    def __init__(self):
        self.dm = DataManager()
        self._screen: TrackerScreen | None = None
        self._wt: WindowTrackerThread | None = None
        self._notify = None
        self._reminder_timer: QTimer | None = None
        self._reminder_sent = False
        self._app_start = datetime.now()
        self._paused_session = None

    def build_widget(self):
        self._screen = TrackerScreen(self.dm)
        self._start_window_tracker()
        self.dm.touch()
        self._reminder_timer = QTimer()
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(REMINDER_CHECK_MS)
        return self._screen

    def set_notify(self, notify_fn):
        self._notify = notify_fn

    def _start_window_tracker(self):
        self._wt = WindowTrackerThread(self.dm)
        self._wt.window_changed.connect(self._on_window)
        self._wt.idle_changed.connect(self._on_idle)
        self._wt.start()
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def _on_window(self, proc: str, title: str):
        if self.dm.is_ignored_process(proc):
            return
        cat_id = self.dm.get_category_for_process(proc, title) or UNCATEGORIZED_ID
        self._screen.auto_start(cat_id, process=proc)

    def _on_idle(self, is_idle: bool):
        if is_idle:
            if self.dm.active_session:
                cat_id = self.dm.active_session["category_id"]
                process = self.dm.active_session.get("process")
                was_auto = self._screen._auto_active if self._screen else False
                self.dm.pause_session()
                self._paused_session = (cat_id, was_auto, process)
                if self._screen:
                    self._screen.refresh()
        else:
            if self._paused_session:
                cat_id, was_auto, process = self._paused_session
                self._paused_session = None
                self.dm.start_session(cat_id, process=process)
                if self._screen:
                    self._screen._auto_active = was_auto
                    self._screen.refresh()

    def _check_reminders(self):
        try:
            self.dm.touch()
            if not self.dm.settings.get("reminders"):
                self._reminder_sent = False
                return
            if self.dm.active_session:
                self._reminder_sent = False
                return
            if self._reminder_sent:
                return
            last = self.dm.get_last_activity_time() or self._app_start
            idle_min = (datetime.now() - last).total_seconds() / 60
            reminder_idle_min = self.dm.settings.get("reminder_idle_min", 30)
            if idle_min >= reminder_idle_min:
                if self._notify:
                    self._notify(
                        "Трекер часу",
                        f"Таймер не активний вже {int(idle_min)} хв. Не забудь розпочати відстеження.",
                    )
                self._reminder_sent = True
        except Exception:
            pass

    def shutdown(self):
        if self._reminder_timer:
            self._reminder_timer.stop()
        if self._wt:
            self._wt.stop()
            self._wt.wait(2000)
        if self.dm.active_session:
            self.dm.stop_session()
        self.dm.touch()
