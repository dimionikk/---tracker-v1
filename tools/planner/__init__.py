from datetime import datetime

from PyQt6.QtCore import QTimer

from tools.base import BaseTool
from tools.logger import log
from tools.notifications import SettingsManager, TelegramSenderThread
from .manager import PlannerManager, time_to_minutes
from .screen import PlannerScreen

CHECK_INTERVAL_MS = 30_000

class PlannerTool(BaseTool):
    TITLE = "Плани"
    ICON = "🗒"

    def __init__(self, settings_manager: SettingsManager = None):
        self.pm = PlannerManager()
        self.sm = settings_manager or SettingsManager()
        self._screen: PlannerScreen | None = None
        self._timer: QTimer | None = None
        self._notify = None
        self._notified = set()
        self._tg_threads = []

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
        try:
            now = datetime.now()
            today_str = now.date().isoformat()
            now_min = now.hour * 60 + now.minute
            lead = int(self.sm.get("reminder_lead_min"))

            self._notified = {k for k in self._notified if k[0] == today_str}

            for e in self.pm.events_for_date(today_str):
                key = (today_str, e["id"])
                if key in self._notified:
                    continue
                delta = time_to_minutes(e["time"]) - now_min
                if 0 <= delta <= lead:
                    self._send_reminder(e)
                    self._notified.add(key)
        except Exception as ex:
            log("PLANNER", f"Помилка перевірки нагадувань: {ex}")

    def _send_reminder(self, e: dict):
        try:
            text = f"{e['title']} о {e['time']}"
            if self._notify and self.sm.get("desktop_enabled"):
                self._notify("Нагадування", text)
                log("PLANNER", f"Надіслано нагадування на робочому столі: {text}")

            if self.sm.get("telegram_enabled"):
                token = self.sm.get("telegram_token")
                chat_id = self.sm.get("telegram_chat_id")
                if token and chat_id:
                    msg = f"⏰ {text}"
                    if self.sm.get("chat_mode") == "group":
                        username = self.sm.get("telegram_username")
                        if username:
                            msg = f"@{username} {msg}"
                    thread = TelegramSenderThread(token, chat_id, msg)
                    thread.finished.connect(lambda t=thread: self._tg_threads.remove(t) if t in self._tg_threads else None)
                    self._tg_threads.append(thread)
                    thread.start()
        except Exception as ex:
            log("PLANNER", f"Помилка надсилання нагадування: {ex}")

    def shutdown(self):
        if self._timer:
            self._timer.stop()
