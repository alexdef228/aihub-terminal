# -*- coding: utf-8 -*-
"""Язык для скриптов, которые живут отдельно от сборки.

Статусная строка и всплывашка копируются установщиком в ~/.claude/aihub,
и texts.py со skin_settings.py туда не едут. Этот модуль едет вместе с ними:
путь к сборке берёт из skin_dir.txt рядом, язык — из её settings.json
(«language»; старый настройки.json с «язык» тоже годится), а без
настройки — по языку Windows.

    from ui_lang import pick
    pick("ГОТОВО", "DONE")
"""
import ctypes
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _detect():
    skin = HERE
    try:
        with open(os.path.join(HERE, "skin_dir.txt"), encoding="utf-8") as handle:
            skin = handle.read().strip() or HERE
    except OSError:
        pass
    for name in ("settings.json", "настройки.json"):
        try:
            with open(os.path.join(skin, name), encoding="utf-8") as handle:
                data = json.load(handle)
            chosen = data.get("language", data.get("язык"))
            if chosen in ("ru", "en"):
                return chosen
            break
        except (OSError, ValueError, AttributeError):
            continue
    try:
        # Младшие 10 бит LANGID — основной язык; 0x19 — русский.
        return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x19 else "en"
    except Exception:
        return "en"


LANG = _detect()


def pick(ru, en):
    return ru if LANG == "ru" else en
