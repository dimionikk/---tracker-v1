#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Спільні утиліти та шляхи, доступні всім інструментам.
"""

from pathlib import Path

from PyQt6.QtWidgets import QLabel, QPushButton

# ──────────────────────────── ШЛЯХИ ────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


# ──────────────────────────── ФОРМАТУВАННЯ ЧАСУ ────────────────────────────

def fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}г {m:02d}хв {s:02d}с"


def fmt_timer(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ──────────────────────────── UI-ХЕЛПЕРИ ────────────────────────────

def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #8E8E93; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;")
    return lbl


def icon_btn(icon: str, callback, data, danger: bool = False) -> QPushButton:
    btn = QPushButton(icon)
    btn.setFixedSize(28, 28)
    color = "#FF453A" if danger else "#FFFFFF"
    btn.setStyleSheet(f"background: #3A3A3C; border-radius: 6px; color: {color}; font-size: 14px;")
    btn.clicked.connect(lambda: callback(data))
    return btn
