from tools.base import BaseTool
from .screen import InstallerScreen


class InstallerTool(BaseTool):
    TITLE = "Інсталер"
    ICON = "⬇"

    def build_widget(self):
        return InstallerScreen()
