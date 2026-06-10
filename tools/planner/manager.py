#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер даних планувальника: події дня та виявлення конфліктів за часом.
"""

import json
import os
import uuid

from tools.common import DATA_DIR

DATA_FILE = DATA_DIR / "planner.json"


# ──────────────────────────── ЧАС ────────────────────────────

def time_to_minutes(time_str: str) -> int:
    """'HH:MM' → кількість хвилин від початку доби."""
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    """Кількість хвилин від початку доби → 'HH:MM' (з переносом через північ)."""
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# ──────────────────────────── МЕНЕДЖЕР ────────────────────────────

class PlannerManager:
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
        return {"events": []}

    # ── Події ──

    def events_for_date(self, date_str: str) -> list:
        """Усі події на дату (YYYY-MM-DD), відсортовані за часом початку."""
        return sorted(
            (e for e in self.data["events"] if e["date"] == date_str),
            key=lambda e: time_to_minutes(e["time"]),
        )

    def get_event(self, event_id: str):
        for e in self.data["events"]:
            if e["id"] == event_id:
                return e
        return None

    def add_event(self, date_str: str, time_str: str, duration: int, title: str) -> dict:
        event = {
            "id": uuid.uuid4().hex,
            "date": date_str,
            "time": time_str,
            "duration": duration,
            "title": title,
        }
        self.data["events"].append(event)
        self.save()
        return event

    def update_event(self, event_id: str, **fields):
        event = self.get_event(event_id)
        if event:
            event.update(fields)
            self.save()

    def delete_event(self, event_id: str):
        self.data["events"] = [e for e in self.data["events"] if e["id"] != event_id]
        self.save()

    @staticmethod
    def find_conflicts(events: list) -> set:
        """Повертає множину id подій, що перетинаються в часі з іншою подією."""
        conflicts = set()
        ranges = []
        for e in events:
            start = time_to_minutes(e["time"])
            ranges.append((e["id"], start, start + e["duration"]))
        for i in range(len(ranges)):
            id1, s1, e1 = ranges[i]
            for j in range(i + 1, len(ranges)):
                id2, s2, e2 = ranges[j]
                if s1 < e2 and s2 < e1:
                    conflicts.add(id1)
                    conflicts.add(id2)
        return conflicts
