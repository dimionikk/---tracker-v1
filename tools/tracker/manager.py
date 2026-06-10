import json
import os
import uuid
from datetime import datetime, timedelta, date

from tools.common import DATA_DIR

DATA_FILE = DATA_DIR / "tracker.json"

class DataManager:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                defaults = self._default()
                for key in defaults:
                    if key not in data:
                        data[key] = defaults[key]
                cutoff = (datetime.now() - timedelta(days=180)).isoformat()
                data['sessions'] = [s for s in data.get('sessions', [])
                                    if s.get('start', '') >= cutoff]
                return data
            except Exception:
                pass
        return self._default()

    def save(self):
        tmp = DATA_FILE.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, DATA_FILE)

    def _default(self) -> dict:
        return {
            "categories": [
                {"id": "study",   "name": "Навчання", "color": "#7B6CF6"},
                {"id": "games",   "name": "Ігри",      "color": "#4CAF50"},
                {"id": "work",    "name": "Робота",    "color": "#2196F3"},
                {"id": "leisure", "name": "Дозвілля",  "color": "#FF9800"},
            ],
            "app_mappings": [],
            "sessions": [],
            "settings": {"autostart": False, "reminders": False},
            "active_session": None,
        }

    @property
    def categories(self) -> list:
        return self.data["categories"]

    @property
    def sessions(self) -> list:
        return self.data["sessions"]

    @property
    def app_mappings(self) -> list:
        return self.data["app_mappings"]

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def active_session(self) -> dict | None:
        return self.data.get("active_session")

    def get_category(self, cat_id: str) -> dict | None:
        return next((c for c in self.categories if c["id"] == cat_id), None)

    def add_category(self, name: str, color: str):
        self.categories.append({"id": str(uuid.uuid4()), "name": name, "color": color})
        self.save()

    def remove_category(self, cat_id: str):
        if self.active_session and self.active_session["category_id"] == cat_id:
            self._commit_active()
        self.data["categories"] = [c for c in self.categories if c["id"] != cat_id]
        self.data["app_mappings"] = [m for m in self.app_mappings if m["category_id"] != cat_id]
        self.save()

    def get_category_for_process(self, process_name: str) -> str | None:
        pl = process_name.lower()
        for m in self.app_mappings:
            if m["process"].lower() == pl:
                return m["category_id"]
        return None

    def add_mapping(self, process: str, category_id: str):
        self.data["app_mappings"] = [m for m in self.app_mappings if m["process"].lower() != process.lower()]
        self.app_mappings.append({"process": process, "category_id": category_id})
        self.save()

    def remove_mapping(self, process: str):
        self.data["app_mappings"] = [m for m in self.app_mappings if m["process"] != process]
        self.save()

    def start_session(self, category_id: str) -> dict:
        if self.active_session:
            self._commit_active()
        session = {
            "id": str(uuid.uuid4()),
            "category_id": category_id,
            "start": datetime.now().isoformat(),
            "end": None,
            "duration": 0,
        }
        self.data["active_session"] = session
        self.save()
        return session

    def stop_session(self) -> dict | None:
        if not self.active_session:
            return None
        return self._commit_active()

    def _commit_active(self) -> dict:
        s = self.active_session
        end = datetime.now()
        start = datetime.fromisoformat(s["start"])
        s["end"] = end.isoformat()
        s["duration"] = max(1, int((end - start).total_seconds()))
        self.sessions.append(s)
        self.data["active_session"] = None
        self.save()
        return s

    def get_today_time(self, category_id: str) -> int:
        today = date.today().isoformat()
        total = sum(
            s["duration"] for s in self.sessions
            if s["category_id"] == category_id
            and s["start"][:10] == today
            and s.get("end")
        )
        if self.active_session and self.active_session["category_id"] == category_id:
            start = datetime.fromisoformat(self.active_session["start"])
            total += int((datetime.now() - start).total_seconds())
        return total

    def get_period_stats(self, period: str) -> dict:
        now = datetime.now()
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            cutoff = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        stats = {c["id"]: 0 for c in self.categories}
        for s in self.sessions:
            if s.get("end") and datetime.fromisoformat(s["start"]) >= cutoff:
                cid = s["category_id"]
                stats[cid] = stats.get(cid, 0) + s["duration"]
        if self.active_session:
            s = self.active_session
            if datetime.fromisoformat(s["start"]) >= cutoff:
                start = datetime.fromisoformat(s["start"])
                cid = s["category_id"]
                stats[cid] = stats.get(cid, 0) + int((datetime.now() - start).total_seconds())
        return stats

    def get_today_sessions(self) -> list:
        today = date.today().isoformat()
        result = [s for s in self.sessions if s["start"][:10] == today and s.get("end")]
        result.sort(key=lambda s: s["start"], reverse=True)
        return result

    def get_day_stats(self, date_str: str) -> dict:
        stats = {c["id"]: 0 for c in self.categories}
        for s in self.sessions:
            if s.get("end") and s["start"][:10] == date_str:
                cid = s["category_id"]
                stats[cid] = stats.get(cid, 0) + s["duration"]
        if self.active_session and self.active_session["start"][:10] == date_str:
            start = datetime.fromisoformat(self.active_session["start"])
            cid = self.active_session["category_id"]
            stats[cid] = stats.get(cid, 0) + int((datetime.now() - start).total_seconds())
        return stats
