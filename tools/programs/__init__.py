from tools.base import BaseTool
from .manager import ProgramsManager
from .screen import ProgramsScreen


class ProgramsTool(BaseTool):
    TITLE = "Програми"
    ICON = "📦"

    def __init__(self):
        self.pm = ProgramsManager()
        self._screen: ProgramsScreen | None = None

    def build_widget(self):
        self._screen = ProgramsScreen(self.pm)
        return self._screen

    def on_activate(self):
        if self._screen:
            self._screen.refresh()
