# -*- coding: utf-8 -*-
"""Связь меню AIHUB с программой «Планы» (TaskNotes) — задачи проектов.

AIHUB menu <-> TaskNotes ("Планы") link. The two programs are installed
independently and find each other through the per-user registry:

    HKCU\\Software\\AIHUB\\TerminalSkin  Dir — папка этого меню. Пишет
                                        register_skin() при каждом запуске
                                        меню и claude-matrix.cmd; по нему
                                        «Планы» открывают Claude в матричном
                                        терминале и берут корни проектов.
    HKCU\\Software\\AIHUB\\TaskNotes     Exe — где стоит plans.exe (ещё Dir,
                                        Version). Пишут сами «Планы» при
                                        каждом запуске.

Вписанных путей нет: нет «Планов» — кнопки «Задачи» в меню нет, файл задач
новому проекту не заводится.

Задачи живут в памяти Claude Code:

    %USERPROFILE%\\.claude\\projects\\<slug>\\memory\\zadachi.md

Claude читает память проекта в каждой сессии, поэтому задачи оттуда он видит
сам, а новые пишет туда же.

    seed(path)        новому проекту — пустой файл задач по шаблону «Планов»
                      и строка-указатель в MEMORY.md (без неё Claude о файле
                      не узнает). Уже есть — ничего не трогает.
    open_plans(path)  открыть «Планы» сразу на этом проекте
                      (plans.exe --project <папка>).
    installed()       стоят ли «Планы» — показывать ли кнопку «Задачи».
    register_skin()   записать в реестр, где лежит это меню.

TEMPLATE и POINTER — те же, что в «Планах» (src-tauri/src/main.rs): это
формат файла, который читает программа, поэтому текст в них не переводится.
"""
import os
import subprocess

from texts import t

HOME = os.environ.get("USERPROFILE") or os.path.expanduser("~")
KEY_SKIN = r"Software\AIHUB\TerminalSkin"
KEY_PLANS = r"Software\AIHUB\TaskNotes"

TASKS_FILE = "zadachi.md"
POINTER = "- [Задачи проекта](zadachi.md) — что осталось сделать; отмечать сделанное"
TEMPLATE = """---
name: zadachi
description: Открытые задачи проекта — что осталось сделать
metadata:
  type: project
---

> Задачи проекта. Файл правят и программа «Планы», и Claude.
> `- [ ]` — открыта, `- [x]` — сделана, 🔨 в начале текста — взята в работу, делать первой.
> Новое «что осталось сделать» дописывать сюда же, сделанное отмечать `[x]`.
"""


def slug(path):
    """Имя папки проекта у Claude Code: всё, кроме латиницы и цифр, — дефис.

    Считается по UTF-16, как в JavaScript внутри Claude Code: кириллица —
    один дефис на букву, эмодзи — два.
    """
    raw = path.encode("utf-16-le")
    out = []
    for i in range(0, len(raw), 2):
        unit = raw[i] | (raw[i + 1] << 8)
        ch = chr(unit) if unit < 128 else ""
        out.append(ch if ch.isascii() and ch.isalnum() else "-")
    return "".join(out)


def memory_dir(path):
    return os.path.join(HOME, ".claude", "projects", slug(path), "memory")


def tasks_file(path):
    return os.path.join(memory_dir(path), TASKS_FILE)


def seed(path):
    """Файл задач и указатель для нового проекта. → None или что не так.
    «Планов» нет — ничего не заводит: файл им и нужен."""
    if not installed():
        return None
    try:
        folder = memory_dir(path)
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, TASKS_FILE)
        if not os.path.exists(target):
            with open(target, "w", encoding="utf-8", newline="\n") as f:
                f.write(TEMPLATE)
        index = os.path.join(folder, "MEMORY.md")
        old = ""
        if os.path.exists(index):
            with open(index, encoding="utf-8") as f:
                old = f.read()
        if "(zadachi.md)" not in old:
            eol = "\r\n" if "\r\n" in old else "\n"
            with open(index, "w", encoding="utf-8", newline="") as f:
                f.write(old + ("" if not old or old.endswith("\n") else eol) + POINTER + eol)
        return None
    except OSError as error:
        return t("plans_seed_failed") + (error.strerror or str(error))


def _read(key, name):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def register_skin():
    """Записать, где лежит меню AIHUB, — «Планы» найдут его по этому ключу."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY_SKIN) as k:
            winreg.SetValueEx(k, "Dir", 0, winreg.REG_SZ, here)
    except OSError:
        pass   # без записи «Планы» просто откроют обычный терминал


def unregister_skin():
    """Убрать ключ AIHUB (install.py --uninstall) — «Планы» перестанут его звать."""
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY_SKIN)
    except OSError:
        pass


def exe():
    """plans.exe по ключу, который пишут сами «Планы»; нет — None."""
    program = _read(KEY_PLANS, "Exe")
    return program if program and os.path.isfile(program) else None


def installed():
    return exe() is not None


def open_plans(path):
    """Открыть «Планы» на проекте. → None или что не так."""
    program = exe()
    if not program:
        return t("plans_missing")
    try:
        # Отдельно от консоли меню: закроется меню — «Планы» останутся
        flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([program, "--project", path], creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return None
    except OSError as error:
        return t("plans_failed") + (error.strerror or str(error))
