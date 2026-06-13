import json
import os
import subprocess
import sys
import tempfile

from tools.common import DATA_DIR

CATALOG_FILE = DATA_DIR / "winget_catalog.json"

# Порядок категорій у каталозі.
CATEGORIES = [
    "Браузери",
    "Комунікації",
    "Розробка",
    "Ігри",
    "Сервіси Microsoft",
    "Мультимедіа",
    "Професійні інструменти",
    "Selfhosted",
    "Утиліти",
]

DEFAULT_CATEGORY = "Інше"


def _default_catalog() -> list[dict]:
    """Каталог програм для встановлення через winget, згрупований
    по 9 категоріях (на основі переліку WinUtil)."""
    return [
        # Браузери
        {"name": "Brave", "id": "Brave.Brave", "category": "Браузери"},
        {"name": "Chrome", "id": "Google.Chrome", "category": "Браузери"},
        {"name": "Chromium", "id": "Hibbiki.Chromium", "category": "Браузери"},
        {"name": "Edge", "id": "Microsoft.Edge", "category": "Браузери"},
        {"name": "Firefox", "id": "Mozilla.Firefox", "category": "Браузери"},
        {"name": "Firefox ESR", "id": "Mozilla.Firefox.ESR", "category": "Браузери"},
        {"name": "Floorp", "id": "Ablaze.Floorp", "category": "Браузери"},
        {"name": "Helium", "id": "ImputNet.Helium", "category": "Браузери"},
        {"name": "LibreWolf", "id": "LibreWolf.LibreWolf", "category": "Браузери"},
        {"name": "Mullvad Browser", "id": "MullvadVPN.MullvadBrowser", "category": "Браузери"},
        {"name": "Tor Browser", "id": "TorProject.TorBrowser", "category": "Браузери"},
        {"name": "Ungoogled", "id": "eloston.ungoogled-chromium", "category": "Браузери"},
        {"name": "Vivaldi", "id": "Vivaldi.Vivaldi", "category": "Браузери"},
        {"name": "Waterfox", "id": "Waterfox.Waterfox", "category": "Браузери"},
        {"name": "Zen Browser", "id": "Zen-Team.Zen-Browser", "category": "Браузери"},
        # Комунікації
        {"name": "Betterbird", "id": "Betterbird.Betterbird", "category": "Комунікації"},
        {"name": "Chatterino", "id": "ChatterinoTeam.Chatterino", "category": "Комунікації"},
        {"name": "Discord", "id": "Discord.Discord", "category": "Комунікації"},
        {"name": "Dorion", "id": "SpikeHD.Dorion", "category": "Комунікації"},
        {"name": "Element", "id": "Element.Element", "category": "Комунікації"},
        {"name": "Proton Mail", "id": "Proton.ProtonMail", "category": "Комунікації"},
        {"name": "QTox", "id": "Tox.qTox", "category": "Комунікації"},
        {"name": "Signal", "id": "OpenWhisperSystems.Signal", "category": "Комунікації"},
        {"name": "Slack", "id": "SlackTechnologies.Slack", "category": "Комунікації"},
        {"name": "Teams", "id": "Microsoft.Teams", "category": "Комунікації"},
        {"name": "TeamSpeak 3", "id": "TeamSpeakSystems.TeamSpeakClient", "category": "Комунікації"},
        {"name": "Telegram", "id": "Telegram.TelegramDesktop", "category": "Комунікації"},
        {"name": "Thunderbird", "id": "Mozilla.Thunderbird", "category": "Комунікації"},
        {"name": "Vesktop", "id": "Vencord.Vesktop", "category": "Комунікації"},
        {"name": "Viber", "id": "Rakuten.Viber", "category": "Комунікації"},
        {"name": "Zoom", "id": "Zoom.Zoom", "category": "Комунікації"},
        # Розробка
        {"name": "Amazon Corretto 21 (LTS)", "id": "Amazon.Corretto.21.JDK", "category": "Розробка"},
        {"name": "Amazon Corretto 25 (LTS)", "id": "Amazon.Corretto.25.JDK", "category": "Розробка"},
        {"name": "Amazon Corretto 8 (LTS)", "id": "Amazon.Corretto.8.JDK", "category": "Розробка"},
        {"name": "CMake", "id": "Kitware.CMake", "category": "Розробка"},
        {"name": "Cursor", "id": "Anysphere.Cursor", "category": "Розробка"},
        {"name": "Git", "id": "Git.Git", "category": "Розробка"},
        {"name": "GitHub Desktop", "id": "GitHub.GitHubDesktop", "category": "Розробка"},
        {"name": "Go", "id": "GoLang.Go", "category": "Розробка"},
        {"name": "Jetbrains Toolbox", "id": "JetBrains.Toolbox", "category": "Розробка"},
        {"name": "Lazygit", "id": "JesseDuffield.lazygit", "category": "Розробка"},
        {"name": "Lua", "id": "rjpcomputing.luaforwindows", "category": "Розробка"},
        {"name": "Neovim", "id": "Neovim.Neovim", "category": "Розробка"},
        {"name": "NodeJS", "id": "OpenJS.NodeJS", "category": "Розробка"},
        {"name": "NodeJS LTS", "id": "OpenJS.NodeJS.LTS", "category": "Розробка"},
        {"name": "Oh My Posh (Prompt)", "id": "JanDeDobbeleer.OhMyPosh", "category": "Розробка"},
        {"name": "Python3", "id": "Python.Python.3.14", "category": "Розробка"},
        {"name": "Ruby", "id": "RubyInstallerTeam.Ruby.4.0", "category": "Розробка"},
        {"name": "Rust", "id": "Rustlang.Rust.MSVC", "category": "Розробка"},
        {"name": "Sublime Text", "id": "SublimeHQ.SublimeText.4", "category": "Розробка"},
        {"name": "System Informer", "id": "WinsiderSS.SystemInformer", "category": "Розробка"},
        {"name": "Unity Game Engine", "id": "Unity.UnityHub", "category": "Розробка"},
        {"name": "uv", "id": "astral-sh.uv", "category": "Розробка"},
        {"name": "Visual Studio 2022", "id": "Microsoft.VisualStudio.2022.Community", "category": "Розробка"},
        {"name": "Visual Studio 2026", "id": "Microsoft.VisualStudio.Community", "category": "Розробка"},
        {"name": "VS Code", "id": "Microsoft.VisualStudioCode", "category": "Розробка"},
        {"name": "VS Codium", "id": "VSCodium.VSCodium", "category": "Розробка"},
        {"name": "Yarn", "id": "Yarn.Yarn", "category": "Розробка"},
        {"name": "Zed", "id": "ZedIndustries.Zed", "category": "Розробка"},
        # Ігри
        {"name": "Cemu", "id": "Cemu.Cemu", "category": "Ігри"},
        {"name": "EA App", "id": "ElectronicArts.EADesktop", "category": "Ігри"},
        {"name": "Epic Games Launcher", "id": "EpicGames.EpicGamesLauncher", "category": "Ігри"},
        {"name": "GeForce NOW", "id": "Nvidia.GeForceNow", "category": "Ігри"},
        {"name": "GOG Galaxy", "id": "GOG.Galaxy", "category": "Ігри"},
        {"name": "Heroic Games Launcher", "id": "HeroicGamesLauncher.HeroicGamesLauncher", "category": "Ігри"},
        {"name": "Itch.io", "id": "ItchIo.Itch", "category": "Ігри"},
        {"name": "Modrinth App", "id": "Modrinth.ModrinthApp", "category": "Ігри"},
        {"name": "Overwolf", "id": "Overwolf.CurseForge", "category": "Ігри"},
        {"name": "Playnite", "id": "Playnite.Playnite", "category": "Ігри"},
        {"name": "Prism Launcher", "id": "PrismLauncher.PrismLauncher", "category": "Ігри"},
        {"name": "Steam", "id": "Valve.Steam", "category": "Ігри"},
        {"name": "Ubisoft Connect", "id": "Ubisoft.Connect", "category": "Ігри"},
        {"name": "Virtual Desktop Streamer", "id": "VirtualDesktop.Streamer", "category": "Ігри"},
        # Сервіси Microsoft
        {"name": ".NET Desktop Runtime 10", "id": "Microsoft.DotNet.DesktopRuntime.10", "category": "Сервіси Microsoft"},
        {"name": ".NET Desktop Runtime 6", "id": "Microsoft.DotNet.DesktopRuntime.6", "category": "Сервіси Microsoft"},
        {"name": ".NET Desktop Runtime 8", "id": "Microsoft.DotNet.DesktopRuntime.8", "category": "Сервіси Microsoft"},
        {"name": ".NET Desktop Runtime 9", "id": "Microsoft.DotNet.DesktopRuntime.9", "category": "Сервіси Microsoft"},
        {"name": "Autoruns", "id": "Microsoft.Sysinternals.Autoruns", "category": "Сервіси Microsoft"},
        {"name": "DISMTools", "id": "CodingWondersSoftware.DISMTools.Stable", "category": "Сервіси Microsoft"},
        {"name": "NTLite", "id": "Nlitesoft.NTLite", "category": "Сервіси Microsoft"},
        {"name": "NuGet", "id": "Microsoft.NuGet", "category": "Сервіси Microsoft"},
        {"name": "OneDrive", "id": "Microsoft.OneDrive", "category": "Сервіси Microsoft"},
        {"name": "PowerShell", "id": "Microsoft.PowerShell", "category": "Сервіси Microsoft"},
        {"name": "PowerToys", "id": "Microsoft.PowerToys", "category": "Сервіси Microsoft"},
        {"name": "Process Explorer", "id": "Microsoft.Sysinternals.ProcessExplorer", "category": "Сервіси Microsoft"},
        {"name": "RDCMan", "id": "Microsoft.Sysinternals.RDCMan", "category": "Сервіси Microsoft"},
        {"name": "SysInternals Process Monitor", "id": "Microsoft.Sysinternals.ProcessMonitor", "category": "Сервіси Microsoft"},
        {"name": "SysInternals TCPView", "id": "Microsoft.Sysinternals.TCPView", "category": "Сервіси Microsoft"},
        {"name": "Visual C++ 2015-2022 32-bit", "id": "Microsoft.VCRedist.2015+.x86", "category": "Сервіси Microsoft"},
        {"name": "Visual C++ 2015-2022 64-bit", "id": "Microsoft.VCRedist.2015+.x64", "category": "Сервіси Microsoft"},
        {"name": "Windows Terminal", "id": "Microsoft.WindowsTerminal", "category": "Сервіси Microsoft"},
        # Мультимедіа
        {"name": "Adobe Acrobat Reader", "id": "Adobe.Acrobat.Reader.64-bit", "category": "Мультимедіа"},
        {"name": "AIMP (Music Player)", "id": "AIMP.AIMP", "category": "Мультимедіа"},
        {"name": "Audacity", "id": "Audacity.Audacity", "category": "Мультимедіа"},
        {"name": "Blender (3D Graphics)", "id": "BlenderFoundation.Blender", "category": "Мультимедіа"},
        {"name": "Calibre", "id": "calibre.calibre", "category": "Мультимедіа"},
        {"name": "EarTrumpet (Audio)", "id": "File-New-Project.EarTrumpet", "category": "Мультимедіа"},
        {"name": "GIMP (Image Editor)", "id": "GIMP.GIMP.3", "category": "Мультимедіа"},
        {"name": "HandBrake", "id": "HandBrake.HandBrake", "category": "Мультимедіа"},
        {"name": "ImageGlass (Image Viewer)", "id": "DuongDieuPhap.ImageGlass", "category": "Мультимедіа"},
        {"name": "IrfanView", "id": "IrfanSkiljan.IrfanView", "category": "Мультимедіа"},
        {"name": "iTunes", "id": "Apple.iTunes", "category": "Мультимедіа"},
        {"name": "K-Lite Codec Standard", "id": "CodecGuide.K-LiteCodecPack.Standard", "category": "Мультимедіа"},
        {"name": "LibreOffice", "id": "TheDocumentFoundation.LibreOffice", "category": "Мультимедіа"},
        {"name": "Media Player Classic - Home Cinema", "id": "clsid2.mpc-hc", "category": "Мультимедіа"},
        {"name": "mpc-qt", "id": "mpc-qt.mpc-qt", "category": "Мультимедіа"},
        {"name": "NAPS2 (Document Scanner)", "id": "Cyanfish.NAPS2", "category": "Мультимедіа"},
        {"name": "nomacs", "id": "nomacs.nomacs", "category": "Мультимедіа"},
        {"name": "Notepad++", "id": "Notepad++.Notepad++", "category": "Мультимедіа"},
        {"name": "OBS Studio", "id": "OBSProject.OBSStudio", "category": "Мультимедіа"},
        {"name": "Obsidian", "id": "Obsidian.Obsidian", "category": "Мультимедіа"},
        {"name": "ONLYOffice Desktop", "id": "ONLYOFFICE.DesktopEditors", "category": "Мультимедіа"},
        {"name": "Paint.NET", "id": "dotPDN.PaintDotNet", "category": "Мультимедіа"},
        {"name": "ShareX (Screenshots)", "id": "ShareX.ShareX", "category": "Мультимедіа"},
        {"name": "VLC (Video Player)", "id": "VideoLAN.VLC", "category": "Мультимедіа"},
        # Професійні інструменти
        {"name": "Advanced IP Scanner", "id": "Famatech.AdvancedIPScanner", "category": "Професійні інструменти"},
        {"name": "Angry IP Scanner", "id": "angryziber.AngryIPScanner", "category": "Професійні інструменти"},
        {"name": "CPU-Z", "id": "CPUID.CPU-Z", "category": "Професійні інструменти"},
        {"name": "Display Driver Uninstaller", "id": "Wagnardsoft.DisplayDriverUninstaller", "category": "Професійні інструменти"},
        {"name": "GPU-Z", "id": "TechPowerUp.GPU-Z", "category": "Професійні інструменти"},
        {"name": "HWiNFO", "id": "REALiX.HWiNFO", "category": "Професійні інструменти"},
        {"name": "HWMonitor", "id": "CPUID.HWMonitor", "category": "Професійні інструменти"},
        {"name": "Mullvad VPN", "id": "MullvadVPN.MullvadVPN", "category": "Професійні інструменти"},
        {"name": "Nmap", "id": "Insecure.Nmap", "category": "Професійні інструменти"},
        {"name": "OpenVPN Connect", "id": "OpenVPNTechnologies.OpenVPNConnect", "category": "Професійні інструменти"},
        {"name": "Proton VPN", "id": "Proton.ProtonVPN", "category": "Професійні інструменти"},
        {"name": "PuTTY", "id": "PuTTY.PuTTY", "category": "Професійні інструменти"},
        {"name": "Simplewall", "id": "Henry++.simplewall", "category": "Професійні інструменти"},
        {"name": "Ventoy", "id": "Ventoy.Ventoy", "category": "Професійні інструменти"},
        {"name": "WinSCP", "id": "WinSCP.WinSCP", "category": "Професійні інструменти"},
        {"name": "WireGuard", "id": "WireGuard.WireGuard", "category": "Професійні інструменти"},
        {"name": "Wireshark", "id": "WiresharkFoundation.Wireshark", "category": "Професійні інструменти"},
        # Selfhosted
        {"name": "Jellyfin Media Player", "id": "Jellyfin.JellyfinMediaPlayer", "category": "Selfhosted"},
        {"name": "Jellyfin Server", "id": "Jellyfin.Server", "category": "Selfhosted"},
        {"name": "Kodi Media Center", "id": "XBMCFoundation.Kodi", "category": "Selfhosted"},
        {"name": "LocalSend", "id": "LocalSend.LocalSend", "category": "Selfhosted"},
        {"name": "Moonlight/GameStream Client", "id": "MoonlightGameStreamingProject.Moonlight", "category": "Selfhosted"},
        {"name": "NetBird", "id": "Netbird.Netbird", "category": "Selfhosted"},
        {"name": "Nextcloud Desktop", "id": "Nextcloud.NextcloudDesktop", "category": "Selfhosted"},
        {"name": "Plex Desktop", "id": "Plex.Plex", "category": "Selfhosted"},
        {"name": "Plex Media Server", "id": "Plex.PlexMediaServer", "category": "Selfhosted"},
        {"name": "Sunshine/GameStream Server", "id": "LizardByte.Sunshine", "category": "Selfhosted"},
        # Утиліти
        {"name": "1Password", "id": "AgileBits.1Password", "category": "Утиліти"},
        {"name": "7-Zip", "id": "7zip.7zip", "category": "Утиліти"},
        {"name": "AnyDesk", "id": "AnyDesk.AnyDesk", "category": "Утиліти"},
        {"name": "AutoHotkey", "id": "AutoHotkey.AutoHotkey", "category": "Утиліти"},
        {"name": "Bitwarden", "id": "Bitwarden.Bitwarden", "category": "Утиліти"},
        {"name": "BlurAutoClicker", "id": "Blur009.BlurAutoClicker", "category": "Утиліти"},
        {"name": "Bulk Crap Uninstaller", "id": "Klocman.BulkCrapUninstaller", "category": "Утиліти"},
        {"name": "Crystal Disk Info", "id": "CrystalDewWorld.CrystalDiskInfo", "category": "Утиліти"},
        {"name": "Crystal Disk Mark", "id": "CrystalDewWorld.CrystalDiskMark", "category": "Утиліти"},
        {"name": "Deskflow", "id": "Deskflow.Deskflow", "category": "Утиліти"},
        {"name": "Ente Auth", "id": "ente-io.auth-desktop", "category": "Утиліти"},
        {"name": "F.lux", "id": "flux.flux", "category": "Утиліти"},
        {"name": "Files", "id": "FilesCommunity.Files", "category": "Утиліти"},
        {"name": "GlazeWM", "id": "glzr-io.glazewm", "category": "Утиліти"},
        {"name": "Google Drive", "id": "Google.GoogleDrive", "category": "Утиліти"},
        {"name": "Hugo", "id": "Hugo.Hugo.Extended", "category": "Утиліти"},
        {"name": "HxD Hex Editor", "id": "MHNexus.HxD", "category": "Утиліти"},
        {"name": "JPEG View", "id": "sylikc.JPEGView", "category": "Утиліти"},
        {"name": "MSEdgeRedirect", "id": "rcmaehl.MSEdgeRedirect", "category": "Утиліти"},
        {"name": "MSI Afterburner", "id": "Guru3D.Afterburner", "category": "Утиліти"},
        {"name": "NanaZip", "id": "M2Team.NanaZip", "category": "Утиліти"},
        {"name": "Nilesoft Shell", "id": "Nilesoft.Shell", "category": "Утиліти"},
        {"name": "NVCleanstall", "id": "TechPowerUp.NVCleanstall", "category": "Утиліти"},
        {"name": "OFGB (Oh Frick Go Back)", "id": "xM4ddy.OFGB", "category": "Утиліти"},
        {"name": "OPAutoClicker", "id": "OPAutoClicker.OPAutoClicker", "category": "Утиліти"},
        {"name": "OpenRGB", "id": "OpenRGB.OpenRGB", "category": "Утиліти"},
        {"name": "Oracle VirtualBox", "id": "Oracle.VirtualBox", "category": "Утиліти"},
        {"name": "Parsec", "id": "Parsec.Parsec", "category": "Утиліти"},
        {"name": "PeaZip", "id": "Giorgiotani.Peazip", "category": "Утиліти"},
        {"name": "Policy Plus", "id": "Fleex255.PolicyPlus", "category": "Утиліти"},
        {"name": "Process Lasso", "id": "BitSum.ProcessLasso", "category": "Утиліти"},
        {"name": "Proton Authenticator", "id": "Proton.ProtonAuthenticator", "category": "Утиліти"},
        {"name": "Proton Drive", "id": "Proton.ProtonDrive", "category": "Утиліти"},
        {"name": "Proton Pass", "id": "Proton.ProtonPass", "category": "Утиліти"},
        {"name": "qBittorrent", "id": "qBittorrent.qBittorrent", "category": "Утиліти"},
        {"name": "Revo Uninstaller", "id": "RevoUninstaller.RevoUninstaller", "category": "Утиліти"},
        {"name": "Rufus Imager", "id": "Rufus.Rufus", "category": "Утиліти"},
        {"name": "SignalRGB", "id": "WhirlwindFX.SignalRgb", "category": "Утиліти"},
        {"name": "Snappy Driver Installer Origin", "id": "GlennDelahoy.SnappyDriverInstallerOrigin", "category": "Утиліти"},
        {"name": "TeamViewer", "id": "TeamViewer.TeamViewer", "category": "Утиліти"},
        {"name": "TightVNC", "id": "GlavSoft.TightVNC", "category": "Утиліти"},
        {"name": "Total Commander", "id": "Ghisler.TotalCommander", "category": "Утиліти"},
        {"name": "TranslucentTB", "id": "CharlesMilette.TranslucentTB", "category": "Утиліти"},
        {"name": "TreeSize Free", "id": "JAMSoftware.TreeSize.Free", "category": "Утиліти"},
        {"name": "UniGetUI", "id": "Devolutions.UniGetUI", "category": "Утиліти"},
        {"name": "VoidTools Everything", "id": "voidtools.Everything", "category": "Утиліти"},
        {"name": "WinRAR", "id": "RARLab.WinRAR", "category": "Утиліти"},
        {"name": "Wise Program Uninstaller (WiseCleaner)", "id": "WiseCleaner.WiseProgramUninstaller", "category": "Утиліти"},
        {"name": "WizTree", "id": "AntibodySoftware.WizTree", "category": "Утиліти"},
    ]

def load_catalog() -> list[dict]:
    """Завантажує каталог winget-програм. Якщо файл відсутній чи пошкоджений —
    створює його з дефолтним набором популярних програм.

    Записи без категорії або з застарілою категорією (з попередньої версії
    каталогу) автоматично перекатегоризуються (за відомим winget Id, або
    "Інше"). Нові програми з дефолтного каталогу, яких ще немає у
    збереженому файлі, додаються автоматично."""
    if CATALOG_FILE.exists():
        try:
            with open(CATALOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                changed = False

                for entry in data:
                    if entry.get("category") not in CATEGORIES:
                        entry["category"] = DEFAULT_CATEGORY
                        changed = True

                existing_ids = {entry.get("id") for entry in data}
                for default_entry in _default_catalog():
                    if default_entry["id"] not in existing_ids:
                        data.append(default_entry)
                        changed = True

                if changed:
                    save_catalog(data)
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


def group_by_category(catalog: list[dict]) -> dict[str, list[dict]]:
    """Групує каталог за категоріями у заданому порядку (CATEGORIES),
    решта категорій додається після них."""
    groups: dict[str, list[dict]] = {}
    for entry in catalog:
        cat = entry.get("category", DEFAULT_CATEGORY)
        groups.setdefault(cat, []).append(entry)

    ordered: dict[str, list[dict]] = {}
    for cat in CATEGORIES:
        if cat in groups:
            ordered[cat] = groups.pop(cat)
    for cat, entries in groups.items():
        ordered[cat] = entries
    return ordered


def install_command(winget_id: str) -> str:
    """Команда winget для встановлення програми за її Id."""
    return (
        f'winget install --id {winget_id} -e '
        f'--accept-package-agreements --accept-source-agreements'
    )


def uninstall_command(winget_id: str) -> str:
    """Команда winget для видалення програми за її Id."""
    return f'winget uninstall --id {winget_id} -e --accept-source-agreements'


def batch_install_command(winget_ids: list[str]) -> str:
    """Команда для послідовного встановлення кількох програм в одній консолі."""
    return ' & '.join(install_command(wid) for wid in winget_ids)


def batch_uninstall_command(winget_ids: list[str]) -> str:
    """Команда для послідовного видалення кількох програм в одній консолі."""
    return ' & '.join(uninstall_command(wid) for wid in winget_ids)


def upgrade_all_command() -> str:
    """Команда winget для оновлення всіх програм, для яких є новіша версія."""
    return (
        'winget upgrade --all '
        '--accept-package-agreements --accept-source-agreements'
    )


def get_installed_ids() -> set[str]:
    """Повертає множину winget Id уже встановлених програм (через
    `winget export`). При помилці або на не-Windows — порожня множина.

    Призначено для виклику у фоновому потоці, бо `winget export`
    може тривати кілька секунд."""
    if sys.platform != "win32":
        return set()

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(tmp_path)  # winget export не перезаписує існуючий файл

        subprocess.run(
            ["winget", "export", "-o", tmp_path, "--accept-source-agreements"],
            capture_output=True, text=True, timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        if not os.path.exists(tmp_path):
            return set()

        with open(tmp_path, encoding="utf-8") as f:
            data = json.load(f)

        ids: set[str] = set()
        for source in data.get("Sources", []):
            for pkg in source.get("Packages", []):
                pkg_id = pkg.get("PackageIdentifier")
                if pkg_id:
                    ids.add(pkg_id)
        return ids
    except Exception:
        return set()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def open_console(command: str | None = None):
    """Відкриває окреме вікно командного рядка.

    Застосунок запущено з правами адміністратора (див. main.pyw), тож
    нове вікно консолі успадковує ті самі права — winget та інші
    команди, що вимагають адмін-доступу, виконуються без додаткових
    запитів UAC.

    Якщо передано команду — виконує її в новому вікні та залишає його
    відкритим (cmd /k), щоб користувач бачив результат."""
    if sys.platform != "win32":
        return
    if command:
        args = ["cmd.exe", "/k", command]
    else:
        args = ["cmd.exe"]
    subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
