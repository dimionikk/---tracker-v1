#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Інструмент «Плани» — денний планувальник: шкала часу, конфлікти,
нагадування в треї за 10 хвилин до події.
"""

from datetime import datetime

from PyQt6.QtCore import QTimer

from tools.base import BaseTool
from .manager import PlannerManager, time_to_minutes
from .screen import PlannerScreen

REMINDER_LEAD_MIN = 10       # за скільки хвилин до події нагадувати
CHECK_INTERVAL_MS = 30_000   # як часто перевіряти події (30 с)


class PlannerTool(BaseTool):
    TITLE = "Плани"
    ICON = "🗒"

    def __init__(self):
        self.pm = PlannerManager()
        self._screen: PlannerScreen | None = None
        self._timer: QTimer | None = None
        self._notify = None
        self._notified = set()  # {(date_str, event_id)} — щоб не нагадувати двічі

    def build_widget(self):
        self._screen = PlannerScreen(self.pm)
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_reminders)
        self._timer.start(CHECK_INTERVAL_MS)
        self._check_reminders()
        return self._screen

    def on_activate(self):
        if self._screen:
            self._screen.refresh()

    def set_notify(self, notify_fn):
        self._notify = notify_fn

    def _check_reminders(self):
        if not self._notify:
            return
        now = datetime.now()
        today_str = now.date().isoformat()
        now_min = now.hour * 60 + now.minute

        # Прибираємо позначки за минулі дні
        self._notified = {k for k in self._notified if k[0] == today_str}

        for e in self.pm.events_for_date(today_str):
            key = (today_str, e["id"])
            if key in self._notified:
                continue
            delta = time_to_minutes(e["time"]) - now_min
            if 0 <= delta <= REMINDER_LEAD_MIN:
                self._notify("Нагадування", f"{e['title']} о {e['time']}")
                self._notified.add(key)

    def shutdown(self):
        if self._timer:
            self._timer.stop()
