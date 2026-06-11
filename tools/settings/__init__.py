from tools.base import BaseTool
from tools.notifications import SettingsManager
from .screen import SettingsScreen


class SettingsTool(BaseTool):
    TITLE = "Сповіщення"
    ICON = "⚙"

    def __init__(self, settings_manager: SettingsManager = None):
        self.sm = settings_manager or SettingsManager()
        self._screen: SettingsScreen | None = None

    def build_widget(self):
        self._screen = SettingsScreen(self.sm)
        return self._screen
