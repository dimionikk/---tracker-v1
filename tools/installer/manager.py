import json
import os
import sys

from PyQt6.QtCore import QObject, QProcess, pyqtSignal

from tools.common import DATA_DIR

CATALOG_FILE = DATA_DIR / "winget_catalog.json"


def _default_catalog() -> list[dict]:
    """Початковий каталог популярних програм із готовими winget Id."""
    return [
        {"name": "Google Chrome", "id": "Google.Chrome"},
        {"name": "Mozilla Firefox", "id": "Mozilla.Firefox"},
        {"name": "Microsoft Edge", "id": "Microsoft.Edge"},
        {"name": "7-Zip", "id": "7zip.7zip"},
        {"name": "WinRAR", "id": "RARLab.WinRAR"},
        {"name": "VLC media player", "id": "VideoLAN.VLC"},
        {"name": "Spotify", "id": "Spotify.Spotify"},
        {"name": "Telegram Desktop", "id": "Telegram.TelegramDesktop"},
        {"name": "Discord", "id": "Discord.Discord"},
        {"name": "WhatsApp", "id": "WhatsApp.WhatsApp"},
        {"name": "Zoom", "id": "Zoom.Zoom"},
        {"name": "Steam", "id": "Valve.Steam"},
        {"name": "Visual Studio Code", "id": "Microsoft.VisualStudioCode"},
        {"name": "Notepad++", "id": "Notepad++.Notepad++"},
        {"name": "Adobe Acrobat Reader", "id": "Adobe.Acrobat.Reader.64-bit"},
        {"name": "GIMP", "id": "GIMP.GIMP"},
        {"name": "OBS Studio", "id": "OBSProject.OBSStudio"},
        {"name": "qBittorrent", "id": "qBittorrent.qBittorrent"},
        {"name": "CCleaner", "id": "Piriform.CCleaner"},
        {"name": "Epic Games Launcher", "id": "EpicGames.EpicGamesLauncher"},
    ]


def load_catalog() -> list[dict]:
    """Завантажує каталог winget-програм. Якщо файл відсутній чи пошкоджений —
    створює його з дефолтним набором популярних програм."""
    if CATALOG_FILE.exists():
        try:
            with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    catalog = _default_catalog()
    save_catalog(catalog)
    return catalog


def save_catalog(catalog: list[dict]):
    tmp = CATALOG_FILE.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CATALOG_FILE)


def install_command(winget_id: str) -> str:
    """Команда winget для встановлення програми за її Id."""
    return (
        f'winget install --id {winget_id} -e '
        f'--accept-package-agreements --accept-source-agreements'
    )


class ConsoleProcess(QObject):
    """Обгортка над персистентним процесом командного рядка, у який можна
    надсилати команди та отримувати вивід у реальному часі.

    Застосунок запускається з правами адміністратора (див. main.pyw), тож
    дочірній процес консолі також працює з підвищеними правами — winget
    та інші команди, що вимагають адмін-доступу, виконуються без додаткових
    запитів UAC."""

    output_received = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_ready_read)
        self._proc.finished.connect(self._on_finished)
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        if sys.platform == "win32":
            shell = os.environ.get("COMSPEC", "cmd.exe")
            self._proc.start(shell, [])
            # Перемикаємо кодову сторінку на UTF-8, щоб кирилиця у виводі
            # відображалась коректно.
            self.write_command("chcp 65001 >nul")
        else:
            self._proc.start("/bin/bash", [])

    def is_running(self) -> bool:
        return self._proc.state() != QProcess.ProcessState.NotRunning

    def write_command(self, command: str):
        if not command:
            return
        if not self._started:
            self.start()
        data = (command + "\r\n").encode("utf-8", errors="replace")
        self._proc.write(data)

    def stop(self):
        if self._proc.state() != QProcess.ProcessState.NotRunning:
            self._proc.kill()
            self._proc.waitForFinished(2000)

    def _on_ready_read(self):
        data = self._proc.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text)

    def _on_finished(self, exit_code, _exit_status):
        self._started = False
        self.finished.emit(exit_code)
