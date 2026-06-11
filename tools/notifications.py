import json
import os
import urllib.request
import urllib.parse

from PyQt6.QtCore import QThread

from tools.common import DATA_DIR
from tools.logger import log

SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "reminder_lead_min": 10,
    "desktop_enabled": True,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": "",
    "telegram_username": "",
    "chat_mode": "group",
}


class SettingsManager:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in data:
                        data[key] = value
                return data
            except Exception:
                pass
        return dict(DEFAULT_SETTINGS)

    def save(self):
        tmp = SETTINGS_FILE.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SETTINGS_FILE)

    def get(self, key):
        return self.data.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
        if key == "telegram_token":
            log("SETTINGS", "Змінено токен Telegram-бота")
        else:
            log("SETTINGS", f"Змінено налаштування: {key} = {value}")


def _telegram_api_call(token: str, method: str, params: dict = None, timeout: int = 8) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def send_telegram_message(token: str, chat_id: str, text: str):
    if not token or not chat_id:
        raise ValueError("Не вказано токен або chat ID")
    result = _telegram_api_call(token, "sendMessage", {"chat_id": chat_id, "text": text})
    if not result.get("ok"):
        err = result.get("description", "Невідома помилка Telegram API")
        log("TELEGRAM", f"Помилка надсилання повідомлення: {err}")
        raise RuntimeError(err)
    log("TELEGRAM", f"Надіслано повідомлення: {text}")
    return result


def fetch_latest_chat_id(token: str, chat_type: str = "group") -> dict | None:
    """Find a chat of the requested type to send reminders to.

    chat_type is either "group" (matches group/supergroup chats) or
    "private" (matches the bot's private chat with the user). Returns the
    most recently active matching chat as a dict with id/type/title, or
    None if no usable chat was found.
    """
    if not token:
        raise ValueError("Не вказано токен")
    result = _telegram_api_call(token, "getUpdates")
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Невідома помилка Telegram API"))
    updates = result.get("result", [])
    if not updates:
        return None

    def chat_from(update: dict):
        for key in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
            obj = update.get(key)
            if obj and "chat" in obj:
                return obj["chat"]
        return None

    wanted_types = ("group", "supergroup") if chat_type == "group" else ("private",)

    found = None
    for update in updates:  # ascending by update_id (oldest -> newest)
        chat = chat_from(update)
        if not chat:
            continue
        if chat.get("type") in wanted_types:
            found = chat

    if not found:
        log("TELEGRAM", "Chat ID не знайдено")
        return None
    chat = {
        "id": str(found["id"]),
        "type": found.get("type", ""),
        "title": found.get("title") or found.get("username") or found.get("first_name") or "",
    }
    log("TELEGRAM", f"Знайдено chat ID: {chat['id']} ({chat['type']} {chat['title']})")
    return chat


class TelegramSenderThread(QThread):
    """Fire-and-forget Telegram message sender that doesn't block the UI."""

    def __init__(self, token: str, chat_id: str, text: str, parent=None):
        super().__init__(parent)
        self._token = token
        self._chat_id = chat_id
        self._text = text

    def run(self):
        try:
            send_telegram_message(self._token, self._chat_id, self._text)
        except Exception as e:
            log("TELEGRAM", f"Не вдалося надіслати повідомлення: {e}")
