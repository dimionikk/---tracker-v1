import json
import os
import subprocess
import sys
import uuid

from tools.common import DATA_DIR

DATA_FILE = DATA_DIR / "programs.json"

# Назви ярликів, які зазвичай не є самою програмою і їх варто пропускати.
_SKIP_KEYWORDS = (
    "uninstall", "видалити", "видалення", "remove",
    "readme", "read me", "довідка", "help",
    "documentation", "документація", "license", "ліцензія",
    "website", "веб-сайт", "support", "update", "changelog",
)

# Папки меню «Пуск», де лежать вбудовані/системні засоби Windows —
# їх не показуємо при автосканування.
_SKIP_DIR_KEYWORDS = (
    "windows tools", "windows administrative tools", "administrative tools",
    "accessories", "system tools", "ease of access", "accessibility",
    "maintenance", "startup",
    "засоби windows", "засоби адміністрування", "адміністрування",
    "стандартні", "спеціальні можливості", "технічне обслуговування",
    "автозавантаження",
)

# Український алфавіт — потрібен для правильного сортування назв,
# бо звичайне порівняння рядків ставить літери "і", "ї", "є", "ґ"
# не на свої місця (вони мають інші номери в Unicode).
_UA_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
_UA_ORDER = {ch: i for i, ch in enumerate(_UA_ALPHABET)}


def _sort_key(name: str):
    """Ключ для алфавітного сортування назв програм: латиниця та цифри
    йдуть за звичайним порядком символів, а кирилиця — за правильним
    порядком українського алфавіту (з урахуванням і/ї/є/ґ)."""
    key = []
    for ch in name.lower():
        if ch in _UA_ORDER:
            key.append((1, _UA_ORDER[ch]))
        else:
            key.append((0, ord(ch)))
    return key


def launch_program(path: str) -> tuple[bool, str]:
    if not path:
        return False, "Шлях до програми не вказано."
    try:
        if sys.platform == "win32":
            os.startfile(path)
        else:
            subprocess.Popen([path])
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Автоматичне сканування встановлених програм
# ---------------------------------------------------------------------------

def _start_menu_dirs() -> list[str]:
    dirs = []
    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        dirs.append(os.path.join(programdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"))
    return [d for d in dirs if os.path.isdir(d)]


def scan_start_menu_programs() -> list[dict]:
    """Сканує ярлики меню «Пуск» і повертає список знайдених програм
    у вигляді [{"name": ..., "path": ...}], відсортований за назвою.

    Вбудовані засоби Windows (з папок «Стандартні», «Засоби Windows» тощо,
    а також усе, що лежить у самому каталозі Windows) пропускаються —
    показуються лише програми, встановлені користувачем."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        return []

    windir = os.environ.get("WINDIR", r"C:\Windows")
    windir_prefix = os.path.normpath(windir).lower() + os.sep

    found = {}
    for base in _start_menu_dirs():
        for root, _dirs, files in os.walk(base):
            rel = os.path.relpath(root, base).lower()
            if any(kw in rel for kw in _SKIP_DIR_KEYWORDS):
                continue
            for fname in files:
                if not fname.lower().endswith(".lnk"):
                    continue
                name = os.path.splitext(fname)[0]
                lname = name.lower()
                if any(kw in lname for kw in _SKIP_KEYWORDS):
                    continue
                try:
                    shortcut = shell.CreateShortcut(os.path.join(root, fname))
                    target = shortcut.Targetpath
                except Exception:
                    continue
                if not target or not target.lower().endswith(".exe"):
                    continue
                if not os.path.exists(target):
                    continue
                if os.path.normpath(target).lower().startswith(windir_prefix):
                    continue
                key = target.lower()
                if key not in found:
                    found[key] = {"name": name, "path": target}

    return sorted(found.values(), key=lambda i: i["name"].lower())


class ProgramsManager:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> dict:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data.setdefault("items", [])
                data.setdefault("ignored", [])
                # Міграція зі старого формату, де ignored — список шляхів (рядків).
                data["ignored"] = [
                    e if isinstance(e, dict) else {"name": os.path.basename(e), "path": e}
                    for e in data["ignored"]
                ]
                return data
            except Exception:
                pass
        return self._default()

    def _default(self) -> dict:
        return {"items": [], "ignored": []}

    def save(self):
        tmp = DATA_FILE.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)

    def list_items(self) -> list:
        return sorted(self.data["items"], key=lambda i: _sort_key(i["name"]))

    def get_item(self, item_id: str):
        for i in self.data["items"]:
            if i["id"] == item_id:
                return i
        return None

    def ignore_item(self, item_id: str):
        """Прибирає програму зі списку і додає її в ігнор-лист,
        щоб вона більше не повертала автосканом."""
        item = self.get_item(item_id)
        if not item:
            return
        self.data["items"] = [i for i in self.data["items"] if i["id"] != item_id]
        key = item["path"].lower()
        if not any(e["path"].lower() == key for e in self.data["ignored"]):
            self.data["ignored"].append({"name": item["name"], "path": item["path"]})
        self.save()

    def list_ignored(self) -> list:
        return sorted(self.data["ignored"], key=lambda i: _sort_key(i["name"]))

    def unignore_item(self, path: str):
        """Повертає програму з ігнор-листа назад у список."""
        key = path.lower()
        entry = next((e for e in self.data["ignored"] if e["path"].lower() == key), None)
        if not entry:
            return
        self.data["ignored"] = [e for e in self.data["ignored"] if e["path"].lower() != key]
        if not any(i["path"].lower() == key for i in self.data["items"]):
            self.data["items"].append({
                "id": uuid.uuid4().hex,
                "name": entry["name"],
                "path": entry["path"],
            })
        self.save()

    def add_item(self, name: str, path: str) -> dict:
        item = {
            "id": uuid.uuid4().hex,
            "name": name,
            "path": path,
        }
        self.data["items"].append(item)
        self.save()
        return item

    def sync_scan(self) -> int:
        """Сканує меню «Пуск» і додає в список нові програми, яких там ще
        немає і які не в ігнор-листі. Повертає кількість доданих програм."""
        found = scan_start_menu_programs()
        existing_paths = {i["path"].lower() for i in self.data["items"]}
        ignored_paths = {e["path"].lower() for e in self.data["ignored"]}
        added = 0
        for prog in found:
            key = prog["path"].lower()
            if key in existing_paths or key in ignored_paths:
                continue
            self.data["items"].append({
                "id": uuid.uuid4().hex,
                "name": prog["name"],
                "path": prog["path"],
            })
            existing_paths.add(key)
            added += 1
        if added:
            self.save()
        return added
