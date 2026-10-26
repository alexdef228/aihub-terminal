# -*- coding: utf-8 -*-
"""Собрать архив для раздачи: dist/AIHUB-Terminal-<версия>.zip

    python build_package.py [путь к aihub-terminal.exe]

Без аргумента exe берётся из сборки в target-next (её делают, пока у
владельца открыто рабочее окно — тогда target\\release занят), иначе из
target\\release. Внутри архива одна папка «AIHUB Терминал»: exe, skin,
установщик. .cmd переводятся в CRLF — с LF cmd.exe рвёт строки.
"""
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(os.path.dirname(HERE), "aihub-terminal")
VERSION = "0.1.0"
TOP = "AIHUB Терминал"


def find_exe():
    if len(sys.argv) > 1:
        return sys.argv[1]
    for sub in ("target-next", "target"):
        p = os.path.join(APP, "src-tauri", sub, "release", "aihub-terminal.exe")
        if os.path.isfile(p):
            return p
    raise SystemExit("exe не найден — сначала собери aihub-terminal")


def crlf(data):
    return data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def main():
    exe = find_exe()
    pkg = os.path.join(HERE, "package")
    os.makedirs(os.path.join(HERE, "dist"), exist_ok=True)
    out = os.path.join(HERE, "dist", "AIHUB-Terminal-{}.zip".format(VERSION))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(exe, TOP + "/AIHUB-Terminal.exe")
        for root, dirs, files in os.walk(pkg):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "session-memory")]
            for name in files:
                if name.endswith(".pyc") or name == "settings.json":
                    continue
                src = os.path.join(root, name)
                rel = os.path.relpath(src, pkg).replace("\\", "/")
                with open(src, "rb") as handle:
                    data = handle.read()
                if name.lower().endswith((".cmd", ".txt")):
                    data = crlf(data)
                z.writestr(TOP + "/" + rel, data)
    print(out, os.path.getsize(out) // 1024, "КБ")


if __name__ == "__main__":
    main()
