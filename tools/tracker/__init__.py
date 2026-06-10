#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Інструмент «Трекер активності».
"""

from PyQt6.QtWidgets import QApplication

from tools.base import BaseTool
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

    # ── Фонове відстеження активного вікна (працює незалежно від вкладки) ──
    def _start_window_tracker(self):
        self._wt = WindowTrackerThread()
        self._wt.window_changed.connect(self._on_window)
        self._wt.start()
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def _on_window(self, proc: str, _title: str):
        cat_id = self.dm.get_category_for_process(proc)
        if cat_id:
            self._screen.auto_start(cat_id)
        else:
            self._screen.auto_stop()

    def shutdown(self):
        if self._wt:
            self._wt.stop()
            self._wt.wait(2000)
