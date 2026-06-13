from PyQt6.QtWidgets import QApplication

from tools.base import BaseTool
from .screen import InstallerScreen


class InstallerTool(BaseTool):
    TITLE = "Встановлення"
    ICON = "⬇"

    def __init__(self):
        self._screen: InstallerScreen | None = None

    def build_widget(self):
        self._screen = InstallerScreen()
        QApplication.instance().aboutToQuit.connect(self.shutdown)
        return self._screen

    def shutdown(self):
        if self._screen:
            self._screen.shutdown()
