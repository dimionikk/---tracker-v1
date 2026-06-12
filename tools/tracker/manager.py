import json
import os
import uuid
from datetime import datetime, timedelta, date

from tools.common import DATA_DIR

DATA_FILE = DATA_DIR / "tracker.json"

DEFAULT_REMINDER_IDLE_MIN = 30
DEFAULT_IDLE_THRESHOLD_MIN = 5

UNCATEGORIZED_ID = "uncategorized"
UNCATEGORIZED_NAME = "Без категорії"
UNCATEGORIZED_COLOR = "#636366"

class DataManager:
    def __init__(self):
        self.data = self._load()
        self._recover_stale_session()
        self._init_self_ignore()

    def _load(self) -> dict:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                defaults = self._default()
                for key in defaults:
                    if key not in data:
                        data[key] = defaults[key]
                for key, val in defaults["settings"].items():
                    if key not in data["settings"]:
                        data["settings"][key] = val
                if not any(c.get("id") == UNCATEGORIZED_ID for c in data.get("categories", [])):
                    data["categories"].append(
                        {"id": UNCATEGORIZED_ID, "name": UNCATEGORIZED_NAME, "color": UNCATEGORIZED_COLOR}
                    )
                cutoff = (datetime.now() - timedelta(days=180)).isoformat()
                data['sessions'] = [s for s in data.get('sessions', [])
                                    if s.get('start', '') >= cutoff]
                return data
            except Exception:
                pass
        return self._default()

    def _init_self_ignore(self):
        """При першому запуску (немає ще жодної сесії й ігнор-лист порожній) додає
        власний процес програми в ігнор-лист, щоб авто-трекер одразу не почав
        рахувати саму програму як «Без категорії»."""
        if self.sessions or self.ignored_processes:
            return
        try:
            import psutil
            own = psutil.Process(os.getpid()).name()
            if own:
                self.data["ignored_processes"].append(own)
                self.save()
        except Exception:
            pass

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
                {"id": UNCATEGORIZED_ID, "name": UNCATEGORIZED_NAME, "color": UNCATEGORIZED_COLOR},
            ],
            "app_mappings": [],
            "ignored_processes": [],
            "sessions": [],
            "settings": {
                "autostart": False,
                "reminders": False,
                "reminder_idle_min": DEFAULT_REMINDER_IDLE_MIN,
                "idle_detection": True,
                "idle_threshold_min": DEFAULT_IDLE_THRESHOLD_MIN,
            },
            "active_session": None,
            "last_seen": None,
        }

    @property
    def categories(self) -> list:
        """Активні (не видалені) категорії — для вибору та керування."""
        return [c for c in self.data["categories"] if not c.get("archived")]

    @property
    def all_categories(self) -> list:
        """Усі категорії, включно з видаленими (потрібні для відображення старих сесій)."""
        return self.data["categories"]

    @property
    def sessions(self) -> list:
        return self.data["sessions"]

    @property
    def app_mappings(self) -> list:
        return self.data["app_mappings"]

    @property
    def ignored_processes(self) -> list:
        return self.data["ignored_processes"]

    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def active_session(self) -> dict | None:
        return self.data.get("active_session")

    def get_category(self, cat_id: str) -> dict | None:
        return next((c for c in self.all_categories if c["id"] == cat_id), None)

    def _find_session(self, session_id: str) -> dict | None:
        return next((x for x in self.sessions if x["id"] == session_id), None)

    def add_category(self, name: str, color: str):
        self.data["categories"].append({"id": str(uuid.uuid4()), "name": name, "color": color})
        self.save()

    def remove_category(self, cat_id: str):
        if cat_id == UNCATEGORIZED_ID:
            return
        cat = self.get_category(cat_id)
        if not cat:
            return
        if self.active_session and self.active_session["category_id"] == cat_id:
            self._commit_active()
        self.data["app_mappings"] = [m for m in self.app_mappings if m["category_id"] != cat_id]
        has_sessions = any(s["category_id"] == cat_id for s in self.sessions)
        if has_sessions:
            # Старі сесії лишаються, але показуються під загальною позначкою
            # «Видалена категорія», щоб не втрачати облік часу.
            cat["name"] = "Видалена категорія"
            cat["color"] = "#48484A"
            cat["archived"] = True
            cat.pop("goal_minutes", None)
            cat.pop("goal_period", None)
        else:
            self.data["categories"] = [c for c in self.data["categories"] if c["id"] != cat_id]
        self.save()

    def get_category_for_process(self, process_name: str, window_title: str = "") -> str | None:
        pl = process_name.lower()
        tl = (window_title or "").lower()
        # Перший прохід: правила з умовою на заголовок вікна
        for m in self.app_mappings:
            if m["process"].lower() == pl and m.get("title_contains"):
                if m["title_contains"].lower() in tl:
                    return m["category_id"]
        # Другий прохід: загальні правила без умови на заголовок
        for m in self.app_mappings:
            if m["process"].lower() == pl and not m.get("title_contains"):
                return m["category_id"]
        return None

    def add_mapping(self, process: str, category_id: str, title_contains: str = ""):
        title_contains = (title_contains or "").strip()
        self.data["app_mappings"] = [
            m for m in self.app_mappings
            if not (m["process"].lower() == process.lower()
                    and m.get("title_contains", "").lower() == title_contains.lower())
        ]
        mapping = {"process": process, "category_id": category_id}
        if title_contains:
            mapping["title_contains"] = title_contains
        self.app_mappings.append(mapping)
        self.save()

    def remove_mapping(self, process: str, title_contains: str = ""):
        title_contains = title_contains or ""
        self.data["app_mappings"] = [
            m for m in self.app_mappings
            if not (m["process"] == process and m.get("title_contains", "") == title_contains)
        ]
        self.save()

    def is_ignored_process(self, process_name: str) -> bool:
        pl = (process_name or "").lower()
        return any(p.lower() == pl for p in self.ignored_processes)

    def add_ignored_process(self, process: str):
        process = (process or "").strip()
        if not process or self.is_ignored_process(process):
            return
        self.data["ignored_processes"].append(process)
        if (self.active_session and self.active_session["category_id"] == UNCATEGORIZED_ID
                and self.active_session.get("process", "").lower() == process.lower()):
            self._commit_active()
        self.save()

    def remove_ignored_process(self, process: str):
        self.data["ignored_processes"] = [
            p for p in self.ignored_processes if p.lower() != (process or "").lower()
        ]
        self.save()

    def start_session(self, category_id: str, process: str | None = None) -> dict:
        if self.active_session:
            self._commit_active()
        session = {
            "id": str(uuid.uuid4()),
            "category_id": category_id,
            "start": datetime.now().isoformat(),
            "end": None,
            "duration": 0,
        }
        if process:
            session["process"] = process
        self.data["active_session"] = session
        self.save()
        return session

    def stop_session(self) -> dict | None:
        if not self.active_session:
            return None
        return self._commit_active()

    def _commit_active(self, end: datetime | None = None) -> dict:
        s = self.active_session
        end = end or datetime.now()
        start = datetime.fromisoformat(s["start"])
        if end <= start:
            end = start + timedelta(seconds=1)
        s["end"] = end.isoformat()
        s["duration"] = max(1, int((end - start).total_seconds()))
        self.sessions.append(s)
        self.data["active_session"] = None
        self.save()
        return s

    def pause_session(self) -> dict | None:
        """Завершує активну сесію станом на момент, коли користувач востаннє був активний
        (зараз мінус поріг бездіяльності), щоб не зараховувати час простою."""
        if not self.active_session:
            return None
        threshold_min = self.settings.get("idle_threshold_min", DEFAULT_IDLE_THRESHOLD_MIN)
        last_active = datetime.now() - timedelta(seconds=threshold_min * 60)
        return self._commit_active(last_active)

    def touch(self):
        """Записує поточний момент як 'останній раз, коли програма була активна'.
        Викликається періодично, поки програма працює, щоб після перезапуску
        можна було коректно завершити сесію, яка лишилась активною (напр. при вимкненні ПК)."""
        self.data["last_seen"] = datetime.now().isoformat()
        self.save()

    def _recover_stale_session(self):
        """Якщо при закритті/вимкненні комп'ютера активна сесія лишилась незавершеною,
        і програма не запускалась довше за поріг бездіяльності — завершує її станом
        на момент останньої активності, а не зараховує весь час, поки ПК був вимкнений."""
        if not self.active_session:
            return
        last_seen_str = self.data.get("last_seen")
        if not last_seen_str:
            return
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
        except (ValueError, TypeError):
            return
        threshold_min = self.settings.get("idle_threshold_min", DEFAULT_IDLE_THRESHOLD_MIN)
        gap_min = (datetime.now() - last_seen).total_seconds() / 60
        if gap_min > threshold_min:
            self._commit_active(last_seen)

    def add_manual_session(self, category_id: str, start: datetime, duration_seconds: int, note: str = "") -> dict:
        end = start + timedelta(seconds=duration_seconds)
        session = {
            "id": str(uuid.uuid4()),
            "category_id": category_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "duration": max(1, int(duration_seconds)),
        }
        note = (note or "").strip()
        if note:
            session["note"] = note
        self.sessions.append(session)
        self.save()
        return session

    def get_last_activity_time(self) -> datetime | None:
        ends = [s["end"] for s in self.sessions if s.get("end")]
        if self.active_session and self.active_session.get("start"):
            ends.append(self.active_session["start"])
        if not ends:
            return None
        return datetime.fromisoformat(max(ends))

    def get_today_time(self, category_id: str) -> int:
        return self.get_period_time(category_id, "day")

    def get_period_time(self, category_id: str, period: str = "day") -> int:
        """Сумарний час для категорії за поточний день/тиждень/місяць (включно з активною сесією)."""
        now = datetime.now()
        if period == "week":
            cutoff = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            cutoff = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = sum(
            s["duration"] for s in self.sessions
            if s["category_id"] == category_id
            and s.get("end")
            and datetime.fromisoformat(s["start"]) >= cutoff
        )
        if self.active_session and self.active_session["category_id"] == category_id:
            start = datetime.fromisoformat(self.active_session["start"])
            total += int((now - start).total_seconds())
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

    def get_sessions_for_day(self, date_str: str) -> list:
        result = [s for s in self.sessions if s["start"][:10] == date_str and s.get("end")]
        result.sort(key=lambda s: s["start"], reverse=True)
        return result

    def get_today_sessions(self) -> list:
        return self.get_sessions_for_day(date.today().isoformat())

    def get_uncategorized_breakdown(self, date_str: str | None = None) -> dict[str, int]:
        """Підсумок часу «Без категорії» за день, згрупований по процесах (для UI авто-трекера).
        Ігноровані процеси не показуються."""
        date_str = date_str or date.today().isoformat()
        result: dict[str, int] = {}
        for s in self.sessions:
            if (s["category_id"] == UNCATEGORIZED_ID and s.get("end")
                    and s["start"][:10] == date_str and s.get("process")
                    and not self.is_ignored_process(s["process"])):
                result[s["process"]] = result.get(s["process"], 0) + s["duration"]
        if (self.active_session and self.active_session["category_id"] == UNCATEGORIZED_ID
                and self.active_session["start"][:10] == date_str and self.active_session.get("process")
                and not self.is_ignored_process(self.active_session["process"])):
            start = datetime.fromisoformat(self.active_session["start"])
            result[self.active_session["process"]] = result.get(self.active_session["process"], 0) \
                + int((datetime.now() - start).total_seconds())
        return result

    def assign_process_category(self, process: str, category_id: str):
        """Створює правило авто-мапінгу для процесу та переносить усі сьогоднішні
        записи «Без категорії» для цього процесу у вибрану категорію."""
        self.add_mapping(process, category_id)
        today = date.today().isoformat()
        pl = process.lower()
        for s in self.sessions:
            if (s["category_id"] == UNCATEGORIZED_ID and s.get("process", "").lower() == pl
                    and s["start"][:10] == today):
                s["category_id"] = category_id
        if (self.active_session and self.active_session["category_id"] == UNCATEGORIZED_ID
                and self.active_session.get("process", "").lower() == pl
                and self.active_session["start"][:10] == today):
            self.active_session["category_id"] = category_id
        self.save()

    def update_session(self, session_id: str, category_id: str, start: datetime, duration_seconds: int,
                        note: str | None = None) -> dict | None:
        """Редагує вже завершений запис: змінює категорію, час початку, тривалість та/або нотатку,
        перераховуючи час завершення як start + duration."""
        s = self._find_session(session_id)
        if not s:
            return None
        s["category_id"] = category_id
        s["start"] = start.isoformat()
        s["duration"] = max(1, int(duration_seconds))
        s["end"] = (start + timedelta(seconds=s["duration"])).isoformat()
        if note is not None:
            note = note.strip()
            if note:
                s["note"] = note
            else:
                s.pop("note", None)
        self.save()
        return s

    def delete_session(self, session_id: str) -> bool:
        """Видаляє завершений запис назавжди."""
        s = self._find_session(session_id)
        if not s:
            return False
        self.data["sessions"] = [x for x in self.sessions if x["id"] != session_id]
        self.save()
        return True

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

    def set_day_category_duration(self, date_str: str, category_id: str, new_seconds: int):
        """Встановлює сумарну тривалість категорії за певний день, підлаштовуючи
        останні завершені записи цієї категорії за цей день (або створюючи/видаляючи їх)."""
        new_seconds = max(0, int(new_seconds))
        sessions = [
            s for s in self.sessions
            if s["category_id"] == category_id and s.get("end") and s["start"][:10] == date_str
        ]
        sessions.sort(key=lambda s: s["start"])
        current_total = sum(s["duration"] for s in sessions)
        delta = new_seconds - current_total
        if delta > 0:
            if sessions:
                last = sessions[-1]
                last["duration"] += delta
                start = datetime.fromisoformat(last["start"])
                last["end"] = (start + timedelta(seconds=last["duration"])).isoformat()
            else:
                start = datetime.fromisoformat(date_str + "T12:00:00")
                session = {
                    "id": str(uuid.uuid4()),
                    "category_id": category_id,
                    "start": start.isoformat(),
                    "end": (start + timedelta(seconds=new_seconds)).isoformat(),
                    "duration": new_seconds,
                }
                self.sessions.append(session)
        elif delta < 0:
            remaining = -delta
            for s in reversed(sessions):
                if remaining <= 0:
                    break
                if s["duration"] <= remaining:
                    remaining -= s["duration"]
                    self.data["sessions"] = [x for x in self.sessions if x["id"] != s["id"]]
                else:
                    s["duration"] -= remaining
                    start = datetime.fromisoformat(s["start"])
                    s["end"] = (start + timedelta(seconds=s["duration"])).isoformat()
                    remaining = 0
        self.save()

    def export_data(self, path: str):
        """Зберігає всі дані трекера (категорії, сесії, налаштування тощо) у JSON-файл."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)

    def import_data(self, path: str):
        """Завантажує дані трекера з JSON-файлу (повністю замінює поточні дані),
        доповнюючи відсутні поля значеннями за замовчуванням."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict) or "categories" not in data or "sessions" not in data:
            raise ValueError("Файл не схожий на бекап даних трекера")
        defaults = self._default()
        for key in defaults:
            if key not in data:
                data[key] = defaults[key]
        for key, val in defaults["settings"].items():
            if key not in data.get("settings", {}):
                data.setdefault("settings", {})[key] = val
        self.data = data
        self.save()

    def find_adjacent_sessions(self, session_id: str) -> tuple:
        """Повертає (попередній, наступний) запис тієї ж категорії в хронологічному
        порядку — для об'єднання сусідніх записів."""
        s = self._find_session(session_id)
        if not s:
            return None, None
        same_cat = sorted(
            (x for x in self.sessions if x["category_id"] == s["category_id"] and x.get("end")),
            key=lambda x: x["start"]
        )
        idx = next((i for i, x in enumerate(same_cat) if x["id"] == session_id), None)
        if idx is None:
            return None, None
        prev_s = same_cat[idx - 1] if idx > 0 else None
        next_s = same_cat[idx + 1] if idx < len(same_cat) - 1 else None
        return prev_s, next_s

    def merge_sessions(self, id_a: str, id_b: str) -> dict | None:
        """Об'єднує два записи (тієї ж категорії) в один, що охоплює обидва періоди часу.
        Видаляє другий запис, повертає оновлений перший."""
        a = self._find_session(id_a)
        b = self._find_session(id_b)
        if not a or not b:
            return None
        start_a, end_a = datetime.fromisoformat(a["start"]), datetime.fromisoformat(a["end"])
        start_b, end_b = datetime.fromisoformat(b["start"]), datetime.fromisoformat(b["end"])
        new_start = min(start_a, start_b)
        new_end = max(end_a, end_b)
        a["start"] = new_start.isoformat()
        a["end"] = new_end.isoformat()
        a["duration"] = max(1, int((new_end - new_start).total_seconds()))
        notes = [x.get("note", "").strip() for x in (a, b) if x.get("note", "").strip()]
        if notes:
            a["note"] = "; ".join(dict.fromkeys(notes))
        else:
            a.pop("note", None)
        self.data["sessions"] = [x for x in self.sessions if x["id"] != id_b]
        self.save()
        return a

    def split_session(self, session_id: str, first_part_seconds: int):
        """Розділяє запис на дві частини: перша триватиме first_part_seconds, друга — решту."""
        s = self._find_session(session_id)
        if not s:
            return None
        total = s["duration"]
        first_part_seconds = max(1, min(int(first_part_seconds), total - 1))
        start = datetime.fromisoformat(s["start"])
        end = datetime.fromisoformat(s["end"])
        split_point = start + timedelta(seconds=first_part_seconds)

        second = {
            "id": str(uuid.uuid4()),
            "category_id": s["category_id"],
            "start": split_point.isoformat(),
            "end": end.isoformat(),
            "duration": total - first_part_seconds,
        }
        s["end"] = split_point.isoformat()
        s["duration"] = first_part_seconds
        self.sessions.append(second)
        self.save()
        return s, second
