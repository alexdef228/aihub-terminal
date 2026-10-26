# -*- coding: utf-8 -*-
"""Закрыли вкладку — процесс уходит следом.

Зачем. WezTerm при закрытии вкладки убивает только свой прямой дочерний
процесс — cmd.exe. Внуки (это меню, launch_agent, консоль Codex, сам Claude
Code) остаются прикреплёнными к псевдоконсоли, а Windows ClosePseudoConsole
ЖДЁТ, пока не отцепится последний клиент. Ждёт он в потоке WezTerm, поэтому
окно замирает целиком и навсегда: закрыл вкладку крестиком — терминал висит.

Замерено 08.09.2026: после закрытия вкладок в системе остались три
осиротевших OpenConsole.exe (родители-wezterm давно мертвы) и живой
codex_console.py, который продолжал крутить свой цикл и жечь ~12% ядра,
рисуя в никуда. Он и держал псевдоконсоль.

Лечение. Каждый наш процесс при старте находит «якорь» — того предка,
которого WezTerm убивает сам, — и ждёт его смерти в фоновом потоке. Умер
якорь — уходим немедленно, освобождая псевдоконсоль. Запущено не под
WezTerm (обычный cmd, Windows Terminal, из-под агента) — сторож молча
не включается и ничего не меняет.
"""
import ctypes
from ctypes import wintypes
import os
import threading

import crash_log

TH32CS_SNAPPROCESS = 0x00000002
SYNCHRONIZE = 0x00100000
INFINITE = 0xFFFFFFFF
MAX_PATH = 260

# Процессы-хозяева окна: их дети и есть вкладки.
HOSTS = ("wezterm-gui.exe", "wezterm.exe")


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * MAX_PATH),
    ]


def snapshot():
    """{pid: (pid родителя, имя exe)} — один снимок таблицы процессов."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if handle in (0, -1, 2 ** 32 - 1):
        return {}
    table = {}
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    try:
        ok = kernel32.Process32First(handle, ctypes.byref(entry))
        while ok:
            table[entry.th32ProcessID] = (
                entry.th32ParentProcessID,
                entry.szExeFile.decode("mbcs", "replace").lower(),
            )
            ok = kernel32.Process32Next(handle, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(handle)
    return table


def anchor(pid=None):
    """PID предка, чей родитель — WezTerm. None, если мы не в его вкладке."""
    table = snapshot()
    pid = os.getpid() if pid is None else pid
    seen = set()
    while pid in table and pid not in seen:
        seen.add(pid)
        parent_pid = table[pid][0]
        parent = table.get(parent_pid)
        if parent is None:
            return None
        if parent[1] in HOSTS:
            return pid
        pid = parent_pid
    return None


def watch(on_close=None):
    """Ждать смерти вкладки в фоне. Возвращает поток или None (не под WezTerm).

    on_close вызывается перед выходом — там убирают то, что переживёт нас
    само по себе: запущенный Claude Code, процесс Codex.
    """
    target = anchor()
    if not target:
        return None
    handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, target)
    if not handle:
        return None

    def wait():
        ctypes.windll.kernel32.WaitForSingleObject(handle, INFINITE)
        # Отметка в общем логе: по ней видно, ушли мы за закрытой
        # вкладкой или упали сами — со стороны это одно и то же.
        crash_log.note('сторож: якорь %d закрылся — выхожу' % target)
        if on_close is not None:
            try:
                on_close()
            except Exception:
                pass
        # Именно _exit: обработчики atexit и finally будут писать в мёртвую
        # консоль и могут заблокироваться — а нам надо освободить её сейчас.
        os._exit(0)

    thread = threading.Thread(target=wait, daemon=True, name="console-guard")
    thread.start()
    return thread


def kill_tree(pid):
    """Снести процесс вместе с потомками. Для on_close."""
    import subprocess
    subprocess.call(["taskkill", "/T", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
