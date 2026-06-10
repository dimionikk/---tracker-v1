from PyQt6.QtWidgets import QWidget

class BaseTool:

    TITLE = "Інструмент"
    ICON = "⚙"

    def build_widget(self) -> QWidget:
        raise NotImplementedError

    def on_activate(self):
        pass

    def on_deactivate(self):
        pass

    def shutdown(self):
        pass

    def set_notify(self, notify_fn):
        pass
