import os

CATEGORY_COLORS = [
    '#7B6CF6', '#4CAF50', '#2196F3', '#FF9800',
    '#FF453A', '#00BCD4', '#E91E63', '#9C27B0'
]

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets").replace("\\", "/")

STYLE = """
QWidget {
    background-color: #1C1C1E;
    color: #FFFFFF;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #2C2C2E; width: 5px; border-radius: 2px;
}
QScrollBar::handle:vertical { background: #48484A; border-radius: 2px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QPushButton {
    background-color: #3A3A3C; color: #FFFFFF;
    border: none; border-radius: 10px; padding: 8px 16px;
}
QPushButton:hover { background-color: #48484A; }
QPushButton:pressed { background-color: #636366; }
QPushButton#accentBtn { background-color: #7B6CF6; }
QPushButton#accentBtn:hover { background-color: #8E7FF8; }
QPushButton#stopBtn {
    background-color: #2C1C1C; color: #FF453A;
    border: 1px solid #FF453A; border-radius: 10px;
}
QPushButton#stopBtn:hover { background-color: #FF453A; color: #FFFFFF; }

QComboBox {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C; border-radius: 10px; padding: 8px 12px;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C;
    selection-background-color: #3A3A3C;
}
QLineEdit {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C; border-radius: 8px; padding: 6px 10px;
}
QLineEdit:focus { border-color: #7B6CF6; }
QLabel { background: transparent; }

QTimeEdit, QSpinBox, QDateEdit {
    background-color: #2C2C2E; color: #FFFFFF;
    border: 1px solid #3A3A3C; border-radius: 8px; padding: 6px 10px;
}
QTimeEdit:focus, QSpinBox:focus, QDateEdit:focus { border-color: #7B6CF6; }
QSpinBox::up-button, QSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button,
QDateEdit::up-button, QDateEdit::down-button { width: 16px; }

QCheckBox::indicator {
    width: 40px; height: 24px; border-radius: 12px;
    background-color: #3A3A3C;
}
QCheckBox::indicator:checked { background-color: #7B6CF6; }

/* ── Чекбокс вибору (масові дії у Встановленні) ── */
QCheckBox#selectCheck { outline: none; spacing: 0px; background: transparent; }
QCheckBox#selectCheck::indicator {
    width: 16px; height: 16px; border-radius: 4px;
    background-color: #2C2C2E; border: 1.5px solid #5A5A5C;
}
QCheckBox#selectCheck::indicator:hover { border-color: #7B6CF6; }
QCheckBox#selectCheck::indicator:checked {
    background-color: #7B6CF6; border: 1.5px solid #7B6CF6;
    image: url(ASSETS_DIR/check.svg);
}

QListWidget {
    background: #2C2C2E; border-radius: 8px;
    border: 1px solid #3A3A3C;
}
QListWidget::item { padding: 6px; }
QListWidget::item:selected { background: #3A3A3C; }

QDialog { background: #1C1C1E; }
QMenu {
    background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px;
}
QMenu::item { padding: 8px 16px; }
QMenu::item:selected { background: #3A3A3C; }

/* ── Перемикач режиму (Встановлення) ── */
QPushButton#modeBtn {
    background-color: #2C2C2E; color: #8E8E93;
    border-radius: 8px; padding: 8px 16px;
}
QPushButton#modeBtn:hover:!checked { background-color: #3A3A3C; }
QPushButton#modeBtn:checked { background-color: #7B6CF6; color: #FFFFFF; }

/* ── Бічна панель інструментів ── */
QWidget#sidebar { background-color: #2C2C2E; }
QPushButton#sidebarBtn {
    background: transparent; color: #8E8E93;
    border-radius: 10px; font-size: 11px; padding: 6px 4px;
}
QPushButton#sidebarBtn:checked { background-color: #3A3A3C; color: #FFFFFF; }
QPushButton#sidebarBtn:hover:!checked { background-color: #323234; }

/* ── Планувальник: блоки подій на шкалі часу ── */
QFrame#eventBlock {
    background-color: #0A84FF; border-radius: 8px;
}
QFrame#eventBlock:hover { background-color: #3895FF; }
QFrame#conflictBlock {
    background-color: #FF453A; border-radius: 8px;
    border: 1px solid #FF8A80;
}
QFrame#conflictBlock:hover { background-color: #FF6259; }
""".replace("ASSETS_DIR", _ASSETS_DIR)
