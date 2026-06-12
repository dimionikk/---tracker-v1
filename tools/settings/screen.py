from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QSpinBox, QCheckBox, QFrame, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import QThread, pyqtSignal

from tools.common import section_label
from tools.notifications import SettingsManager, send_telegram_message, fetch_latest_chat_id


class _ApiThread(QThread):
    done = pyqtSignal(bool, object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.done.emit(True, result or "")
        except Exception as e:
            self.done.emit(False, str(e))


def _card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setStyleSheet("QFrame { background: #2C2C2E; border-radius: 10px; }")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 12, 12, 12)
    lay.setSpacing(10)
    return frame, lay


class SettingsScreen(QWidget):
    def __init__(self, sm: SettingsManager):
        super().__init__()
        self.sm = sm
        self._thread: QThread | None = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        title = QLabel("Сповіщення")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        lay.addWidget(title)

        # --- General ---
        lay.addWidget(section_label("ЗАГАЛЬНЕ"))
        general, gl = _card()

        self.desktop_chk = QCheckBox("Сповіщення на робочому столі")
        self.desktop_chk.setChecked(bool(self.sm.get("desktop_enabled")))
        self.desktop_chk.toggled.connect(lambda v: self.sm.set("desktop_enabled", v))
        gl.addWidget(self.desktop_chk)

        lead_row = QHBoxLayout()
        lead_row.addWidget(QLabel("Нагадувати за"))
        self.lead_spin = QSpinBox()
        self.lead_spin.setRange(1, 180)
        self.lead_spin.setSuffix(" хв")
        self.lead_spin.setValue(int(self.sm.get("reminder_lead_min")))
        self.lead_spin.valueChanged.connect(lambda v: self.sm.set("reminder_lead_min", v))
        lead_row.addWidget(self.lead_spin)
        lead_row.addWidget(QLabel("до початку події"))
        lead_row.addStretch()
        gl.addLayout(lead_row)

        lay.addWidget(general)

        # --- Telegram ---
        lay.addWidget(section_label("TELEGRAM"))
        tg, tgl = _card()

        self.tg_chk = QCheckBox("Надсилати сповіщення в Telegram")
        self.tg_chk.setChecked(bool(self.sm.get("telegram_enabled")))
        self.tg_chk.toggled.connect(lambda v: self.sm.set("telegram_enabled", v))
        tgl.addWidget(self.tg_chk)

        tgl.addWidget(section_label("КУДИ НАДСИЛАТИ"))
        mode_row = QHBoxLayout()
        self.mode_group_radio = QRadioButton("У групу (mute + @згадка)")
        self.mode_private_radio = QRadioButton("У приватний чат з ботом")
        self._mode_btn_group = QButtonGroup(self)
        self._mode_btn_group.addButton(self.mode_group_radio)
        self._mode_btn_group.addButton(self.mode_private_radio)
        if self.sm.get("chat_mode") == "private":
            self.mode_private_radio.setChecked(True)
        else:
            self.mode_group_radio.setChecked(True)
        self.mode_group_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.mode_group_radio)
        mode_row.addWidget(self.mode_private_radio)
        mode_row.addStretch()
        tgl.addLayout(mode_row)

        tgl.addWidget(section_label("ТОКЕН БОТА"))
        self.token_input = QLineEdit(self.sm.get("telegram_token"))
        self.token_input.setPlaceholderText("Отримати у @BotFather (команда /newbot)")
        self.token_input.editingFinished.connect(
            lambda: self.sm.set("telegram_token", self.token_input.text().strip())
        )
        tgl.addWidget(self.token_input)

        tgl.addWidget(section_label("CHAT ID"))
        chat_row = QHBoxLayout()
        self.chat_id_input = QLineEdit(self.sm.get("telegram_chat_id"))
        self.chat_id_input.setPlaceholderText("Натисніть «Визначити» нижче")
        self.chat_id_input.editingFinished.connect(
            lambda: self.sm.set("telegram_chat_id", self.chat_id_input.text().strip())
        )
        chat_row.addWidget(self.chat_id_input, 1)
        self.detect_btn = QPushButton("Визначити")
        self.detect_btn.clicked.connect(self._detect_chat_id)
        chat_row.addWidget(self.detect_btn)
        tgl.addLayout(chat_row)

        self.username_label = section_label("ВАШ USERNAME (БЕЗ @)")
        tgl.addWidget(self.username_label)
        self.username_input = QLineEdit(self.sm.get("telegram_username"))
        self.username_input.setPlaceholderText("напр. ivan_petrenko")
        self.username_input.editingFinished.connect(
            lambda: self.sm.set("telegram_username", self.username_input.text().strip().lstrip("@"))
        )
        tgl.addWidget(self.username_input)

        self.hint_lbl = QLabel("")
        self.hint_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        self.hint_lbl.setWordWrap(True)
        tgl.addWidget(self.hint_lbl)

        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Надіслати тестове повідомлення")
        self.test_btn.setObjectName("accentBtn")
        self.test_btn.clicked.connect(self._send_test)
        test_row.addWidget(self.test_btn)
        test_row.addStretch()
        tgl.addLayout(test_row)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setStyleSheet("font-size: 12px; color: #8E8E93;")
        tgl.addWidget(self.status_lbl)

        lay.addWidget(tg)
        lay.addStretch()

        self._update_mode_ui()

    def _on_mode_changed(self, _checked: bool):
        mode = "group" if self.mode_group_radio.isChecked() else "private"
        self.sm.set("chat_mode", mode)
        self._update_mode_ui()

    def _update_mode_ui(self):
        is_group = self.mode_group_radio.isChecked()
        self.username_label.setVisible(is_group)
        self.username_input.setVisible(is_group)
        if is_group:
            self.hint_lbl.setText(
                "1. Створіть бота через @BotFather, вставте сюди токен.\n"
                "2. Створіть групу в Telegram і додайте туди бота.\n"
                "3. Напишіть у групі команду /start (щоб бот побачив групу).\n"
                "4. Натисніть «Визначити» — chat ID групи підставиться автоматично.\n"
                "5. Вкажіть свій username вище.\n"
                "6. Заглушіть сповіщення групи (mute) — Telegram все одно дзвонитиме на згадки @username."
            )
        else:
            self.hint_lbl.setText(
                "1. Створіть бота через @BotFather, вставте сюди токен.\n"
                "2. Напишіть боту команду /start у приватному чаті.\n"
                "3. Натисніть «Визначити» — підставиться ID приватного чату.\n"
                "4. НЕ заглушуйте (mute) цей чат з ботом — інакше сповіщення будуть без звуку."
            )

    def _set_status(self, ok: bool, text: str):
        color = "#4CAF50" if ok else "#FF453A"
        self.status_lbl.setStyleSheet(f"font-size: 12px; color: {color};")
        self.status_lbl.setText(text)

    def _run_async(self, fn, on_done):
        if self._thread and self._thread.isRunning():
            return
        self._thread = _ApiThread(fn, self)
        self._thread.done.connect(on_done)
        self._thread.start()

    def _detect_chat_id(self):
        token = self.token_input.text().strip()
        self.sm.set("telegram_token", token)
        if not token:
            self._set_status(False, "Спочатку введіть токен бота.")
            return
        self._set_status(True, "Шукаємо chat ID…")
        self.detect_btn.setEnabled(False)
        chat_mode = self.sm.get("chat_mode")

        def task():
            chat = fetch_latest_chat_id(token, chat_mode)
            if not chat:
                if chat_mode == "group":
                    raise RuntimeError(
                        "Групу не знайдено. Додайте бота в групу, напишіть там /start і спробуйте ще раз."
                    )
                raise RuntimeError(
                    "Приватний чат не знайдено. Напишіть боту /start і спробуйте ще раз."
                )
            return chat

        def done(ok, result):
            self.detect_btn.setEnabled(True)
            if ok:
                chat_id = result["id"]
                self.chat_id_input.setText(chat_id)
                self.sm.set("telegram_chat_id", chat_id)
                kind = {"group": "група", "supergroup": "група", "private": "особистий чат"}.get(result["type"], result["type"])
                title = f" «{result['title']}»" if result["title"] else ""
                self._set_status(True, f"Знайдено: {kind}{title} (chat ID {chat_id})")
            else:
                self._set_status(False, result)

        self._run_async(task, done)

    def _send_test(self):
        token = self.token_input.text().strip()
        chat_id = self.chat_id_input.text().strip()
        username = self.username_input.text().strip().lstrip("@")
        self.sm.set("telegram_token", token)
        self.sm.set("telegram_chat_id", chat_id)
        self.sm.set("telegram_username", username)
        if not token or not chat_id:
            self._set_status(False, "Вкажіть токен бота і chat ID.")
            return
        self._set_status(True, "Надсилаємо…")
        self.test_btn.setEnabled(False)
        chat_mode = self.sm.get("chat_mode")

        def task():
            text = "✅ Тестове повідомлення з Планувальника"
            if chat_mode == "group" and username:
                text = f"@{username} {text}"
            send_telegram_message(token, chat_id, text)
            return "Надіслано! Перевірте Telegram."

        def done(ok, result):
            self.test_btn.setEnabled(True)
            self._set_status(ok, result if ok else f"Помилка: {result}")

        self._run_async(task, done)
