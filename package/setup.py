# -*- coding: utf-8 -*-
"""Установка AIHUB Терминала. Запускается из «Установить.cmd»; повторный
запуск безопасен — так же ставится и обновление.

Что делает:
  1. копирует программу в %LOCALAPPDATA%\\Programs\\AIHUB Terminal
     (свои настройки и история при обновлении не затираются);
  2. проверяет Claude Code; нет — предлагает поставить (Node.js + npm);
  3. подключает статусную строку Claude Code — по ней окно видит лимиты
     и размер контекста; чужую строку заменяет только с согласия;
  4. ярлыки «AIHUB Терминал» на рабочем столе и в меню «Пуск»;
  5. запускает окно.

    python setup.py              установить / обновить
    python setup.py --uninstall  удалить (папки проектов не трогаются)
"""
import json
import os
import shutil
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
LOCAL = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local")
DEST = os.path.join(LOCAL, "Programs", "AIHUB Terminal")
EXE_NAME = "AIHUB-Terminal.exe"
CLAUDE_SETTINGS = os.path.join(HOME, ".claude", "settings.json")
SHORTCUT = "AIHUB Терминал.lnk"
# Своё у каждого человека — при обновлении не перезаписывается
KEEP = {"settings.json", "session-memory"}

DEFAULT_SETTINGS = {
    "language": "ru",
    "live_background": False,
    "roots": [],
    "extra": [],
    "oneoff_dir": "~",
    "temp_dir": os.path.join("~", "AIHUB", "временные проекты"),
    "marks_file": os.path.join("~", ".claude", "aihub-projects.json"),
    "marks_key": "temporary",
}


def say(text=""):
    print("  " + text)


def step(text):
    print()
    print(" ▓▒░ " + text)


def ask(question, default=True):
    hint = "[Д/н]" if default else "[д/Н]"
    try:
        answer = input("  " + question + " " + hint + " ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer[0] in "дyl"   # «д», «y», и «l» — «д» в английской раскладке


def powershell(script, **env):
    """Пути с кириллицей передаются переменными окружения, не внутри кода."""
    full = dict(os.environ, **env)
    return subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                          env=full, capture_output=True, timeout=60)


def special_folder(name):
    out = powershell("[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Environment]::GetFolderPath('%s')" % name)
    path = out.stdout.decode("utf-8", errors="replace").strip()
    return path if path and os.path.isdir(path) else None


# ── 1. файлы ──────────────────────────────────────────────────────────────

def running():
    """PID окон, запущенных именно из DEST. Только по полному пути: по имени
    нельзя — Windows сравнивает имена без регистра, и под «AIHUB-Terminal.exe»
    попадает любой aihub-terminal.exe, собранный из исходников (26.10.2026
    проверка установщика так трижды закрыла рабочее окно владельца)."""
    out = powershell("Get-Process | Where-Object { $_.Path -eq $env:AIHUB_EXE } | ForEach-Object { $_.Id }",
                     AIHUB_EXE=os.path.join(DEST, EXE_NAME))
    return [int(x) for x in out.stdout.decode("ascii", errors="ignore").split() if x.isdigit()]


def close_running():
    pids = running()
    for pid in pids:
        subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
    for _ in range(20):
        if not running():
            return
        time.sleep(0.5)
    for pid in running():
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    time.sleep(1)


def copy_files():
    if running():
        say("Окно AIHUB Терминала открыто — для обновления его надо закрыть.")
        if not ask("Закрыть его сейчас?"):
            raise SystemExit("  Установка остановлена: окно открыто.")
        close_running()
    os.makedirs(DEST, exist_ok=True)
    shutil.copy2(os.path.join(HERE, EXE_NAME), os.path.join(DEST, EXE_NAME))
    for name in ("setup.py", "Удалить.cmd", "ПРОЧТИ.txt"):
        if os.path.exists(os.path.join(HERE, name)):
            shutil.copy2(os.path.join(HERE, name), os.path.join(DEST, name))
    src_skin, dst_skin = os.path.join(HERE, "skin"), os.path.join(DEST, "skin")
    os.makedirs(dst_skin, exist_ok=True)
    for name in os.listdir(src_skin):
        if name in KEEP or name == "__pycache__":
            continue
        src = os.path.join(src_skin, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_skin, name))
    settings = os.path.join(dst_skin, "settings.json")
    if not os.path.exists(settings):
        with open(settings, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_SETTINGS, handle, ensure_ascii=False, indent=2)
    say("программа в " + DEST)


# ── 2. Claude Code ────────────────────────────────────────────────────────

def claude_found():
    npm_exe = os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules", "@anthropic-ai",
                           "claude-code", "bin", "claude.exe")
    native = os.path.join(HOME, ".local", "bin", "claude.exe")
    return any(os.path.isfile(p) for p in (npm_exe, native)) or bool(shutil.which("claude"))


def npm_path():
    found = shutil.which("npm.cmd") or shutil.which("npm")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.path.join(LOCAL, "Programs")):
        p = os.path.join(base, "nodejs", "npm.cmd")
        if os.path.isfile(p):
            return p
    return None


def winget(package):
    say("ставлю " + package + " через winget (пара минут)…")
    code = subprocess.call(["winget", "install", "--id", package, "-e", "--accept-package-agreements",
                            "--accept-source-agreements", "--disable-interactivity"])
    return code == 0


def ensure_claude():
    if claude_found():
        say("Claude Code уже стоит")
        return
    say("Claude Code не найден. Без него окно запустится, но работать будет некому.")
    if not ask("Поставить Claude Code сейчас?"):
        say("Пропускаю. Поставить потом: npm install -g @anthropic-ai/claude-code")
        return
    npm = npm_path()
    if not npm:
        if not shutil.which("winget"):
            say("Нет ни Node.js, ни winget. Поставь Node.js LTS с nodejs.org и запусти установку ещё раз.")
            return
        winget("OpenJS.NodeJS.LTS")
        npm = npm_path()
    if not npm:
        say("Node.js не нашёлся после установки. Перезапусти «Установить.cmd».")
        return
    say("ставлю Claude Code…")
    subprocess.call([npm, "install", "-g", "@anthropic-ai/claude-code"])
    say("Claude Code поставлен" if claude_found() else "Claude Code не встал — смотри сообщения npm выше.")


# ── 3. статусная строка ───────────────────────────────────────────────────

def statusline_command():
    script = os.path.join(DEST, "skin", "statusline.py").replace("\\", "/")
    return '"{}" "{}"'.format(sys.executable.replace("\\", "/"), script)


def is_ours(command):
    return "statusline.py" in (command or "") and "aihub" in (command or "").lower()


def install_statusline():
    values = {}
    if os.path.exists(CLAUDE_SETTINGS):
        try:
            with open(CLAUDE_SETTINGS, encoding="utf-8-sig") as handle:
                values = json.load(handle)
        except ValueError:
            say("~/.claude/settings.json не читается (битый JSON) — статусную строку не трогаю.")
            return
    current = (values.get("statusLine") or {}).get("command")
    if current and not is_ours(current):
        say("У тебя уже есть своя статусная строка Claude Code:")
        say("  " + current)
        say("Без строки AIHUB окно не покажет лимиты и размер контекста.")
        if not ask("Заменить её на строку AIHUB? (старая сохранится в копии)", default=False):
            say("Оставил как есть.")
            return
    if os.path.exists(CLAUDE_SETTINGS):
        copy = CLAUDE_SETTINGS + ".aihub-backup-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(CLAUDE_SETTINGS, copy)
        say("прежний settings.json сохранён: " + copy)
    values["statusLine"] = {"type": "command", "command": statusline_command(), "refreshInterval": 1}
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS), exist_ok=True)
    with open(CLAUDE_SETTINGS, "w", encoding="utf-8") as handle:
        json.dump(values, handle, ensure_ascii=False, indent=2)
    say("статусная строка подключена — лимиты будут видны в окне")


# ── 4. ярлыки ─────────────────────────────────────────────────────────────

LNK_SCRIPT = (
    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:AIHUB_LNK);"
    "$s.TargetPath=$env:AIHUB_EXE;$s.WorkingDirectory=$env:AIHUB_DIR;"
    "$s.IconLocation=$env:AIHUB_EXE+',0';$s.Description='AIHUB Терминал';$s.Save()"
)


def shortcut_places():
    places = []
    desk = special_folder("Desktop")
    if desk:
        places.append(desk)
    start = special_folder("Programs")
    if start:
        places.append(start)
    return places


def install_shortcuts():
    exe = os.path.join(DEST, EXE_NAME)
    for folder in shortcut_places():
        lnk = os.path.join(folder, SHORTCUT)
        out = powershell(LNK_SCRIPT, AIHUB_LNK=lnk, AIHUB_EXE=exe, AIHUB_DIR=DEST)
        say(("ярлык: " if out.returncode == 0 else "ярлык не создался: ") + lnk)


# ── удаление ──────────────────────────────────────────────────────────────

def uninstall():
    step("Удаляю AIHUB Терминал")
    if running():
        close_running()
    for folder in shortcut_places():
        lnk = os.path.join(folder, SHORTCUT)
        if os.path.exists(lnk):
            os.remove(lnk)
            say("убран ярлык " + lnk)
    if os.path.exists(CLAUDE_SETTINGS):
        try:
            with open(CLAUDE_SETTINGS, encoding="utf-8-sig") as handle:
                values = json.load(handle)
            if is_ours((values.get("statusLine") or {}).get("command")):
                del values["statusLine"]
                with open(CLAUDE_SETTINGS, "w", encoding="utf-8") as handle:
                    json.dump(values, handle, ensure_ascii=False, indent=2)
                say("статусная строка AIHUB убрана из Claude Code")
        except ValueError:
            pass
    say("Папку программы удалю после закрытия этого окна: " + DEST)
    # Сам setup.py лежит в DEST — удаляем отложенно, отдельным cmd.
    subprocess.Popen('cmd /c timeout /t 3 >nul & rmdir /s /q "{}"'.format(DEST),
                     creationflags=0x08000000)
    say("Готово. Папки с проектами и сессии Claude не тронуты.")


def main():
    if "--uninstall" in sys.argv:
        return uninstall()
    print()
    print(" ▓▒░ AIHUB Терминал — установка ░▒▓")
    if not os.path.exists(os.path.join(HERE, EXE_NAME)):
        raise SystemExit("  Рядом нет " + EXE_NAME + ". Распакуй архив целиком и запусти «Установить.cmd» из него.")
    step("1/4  Копирую программу")
    copy_files()
    step("2/4  Claude Code")
    ensure_claude()
    step("3/4  Лимиты в окне")
    install_statusline()
    step("4/4  Ярлыки")
    install_shortcuts()
    print()
    say("Готово! Запускаю AIHUB Терминал.")
    say("В окне: «＋ Новая вкладка» → «📁 Папки с проектами» → покажи, где лежат твои проекты.")
    subprocess.Popen([os.path.join(DEST, EXE_NAME)], cwd=DEST)


if __name__ == "__main__":
    main()
