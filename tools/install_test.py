# -*- coding: utf-8 -*-
"""Проверка пакета на чистом подставном профиле: распаковать архив,
поставить, погонять мост установленной копии, удалить.

Настоящие ~/.claude, рабочий стол и %LOCALAPPDATA% не трогаются: профиль
подменяется переменными окружения, ярлыки идут во временную папку.

    python tools/install_test.py            оставит профиль и напечатает путь
"""
import builtins
import glob
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ZIP = sorted(glob.glob(os.path.join(HERE, "..", "dist", "AIHUB-Terminal-*.zip")))[-1]
TMP = tempfile.mkdtemp(prefix="aihub-install-")
HOME = os.path.join(TMP, "home")
for k, v in {"USERPROFILE": HOME, "HOME": HOME,
             "LOCALAPPDATA": os.path.join(HOME, "AppData", "Local"),
             "APPDATA": os.path.join(HOME, "AppData", "Roaming")}.items():
    os.makedirs(v, exist_ok=True)
    os.environ[k] = v
DESK = os.path.join(TMP, "desktop")
os.makedirs(DESK)


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        raise SystemExit(1)


with zipfile.ZipFile(ZIP) as z:
    z.extractall(os.path.join(TMP, "unz"))
pkg = os.path.join(TMP, "unz", "AIHUB Терминал")
check(os.path.isfile(os.path.join(pkg, "AIHUB-Terminal.exe")), "в архиве exe")
with open(os.path.join(pkg, "Установить.cmd"), "rb") as h:
    raw = h.read()
check(b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"") and not raw.startswith(b"\xef\xbb\xbf"),
      "Установить.cmd — CRLF без BOM")

# Чужая статусная строка — установщик должен спросить и сохранить копию
os.makedirs(os.path.join(HOME, ".claude"))
with open(os.path.join(HOME, ".claude", "settings.json"), "w", encoding="utf-8") as h:
    json.dump({"statusLine": {"type": "command", "command": "node my-line.js"}, "theme": "dark"}, h)

spec = importlib.util.spec_from_file_location("setup_under_test", os.path.join(pkg, "setup.py"))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)
check(setup.DEST.startswith(HOME), "ставится в подставной профиль: " + setup.DEST)
setup.shortcut_places = lambda: [DESK]
# Проверка не закрывает никаких окон — ни своих, ни чужих (26.10.2026 старый
# поиск по имени закрыл рабочее aihub-terminal.exe владельца).
check(setup.running() == [], "открытые aihub-terminal.exe не из папки установки — не наши")


def never(*a, **k):
    raise AssertionError("проверка установки пыталась закрыть окно")


setup.close_running = never
answers = iter(["д"])
builtins.input = lambda prompt="": (print(prompt + "[тест]"), next(answers, ""))[1]

setup.copy_files()
setup.install_statusline()
setup.install_shortcuts()

skin = os.path.join(setup.DEST, "skin")
check(os.path.isfile(os.path.join(setup.DEST, "AIHUB-Terminal.exe")), "exe скопирован")
with open(os.path.join(skin, "settings.json"), encoding="utf-8") as h:
    st = json.load(h)
check(st["roots"] == [] and st["extra"] == [], "settings.json: папок нет — человек добавит сам")
with open(os.path.join(HOME, ".claude", "settings.json"), encoding="utf-8") as h:
    cs = json.load(h)
check("statusline.py" in cs["statusLine"]["command"] and cs.get("theme") == "dark",
      "статусная строка подключена, чужие настройки на месте")
check(glob.glob(os.path.join(HOME, ".claude", "settings.json.aihub-backup-*")), "копия прежнего settings.json")
check(os.path.isfile(os.path.join(DESK, setup.SHORTCUT)), "ярлык создан")

# Статусная строка пишет файл лимитов для окна
line = subprocess.run([sys.executable, os.path.join(skin, "statusline.py")], input=json.dumps({
    "session_id": "t1", "workspace": {"current_dir": TMP}, "model": {"display_name": "Sonnet"},
    "rate_limits": {"five_hour": {"used_percentage": 12}}}).encode(), capture_output=True,
    env=dict(os.environ, AIHUB_TAB="tab9"))
status = os.path.join(os.environ["LOCALAPPDATA"], "AIHUB", "status", "tab-tab9.json")
check(line.returncode == 0 and os.path.isfile(status), "statusline.py кладёт лимиты для окна")

# Мост — тот, что вшит в exe, — на установленном скине
BRIDGE = os.path.join(HERE, "..", "..", "aihub-terminal", "bridge", "aihub_bridge.py")


def bridge(*args):
    out = subprocess.run([sys.executable, BRIDGE, skin] + list(args), capture_output=True)
    return json.loads(out.stdout.decode("utf-8"))


d = bridge("projects")
check(d.get("roots_editable") is True and d["roots"] == [], "мост: папки можно менять, пока пусто")
check([i for i in d["items"] if not i["temp"]] == [], "постоянных проектов нет")
projects = os.path.join(TMP, "Мои проекты")
for n in ("сайт", "bot"):
    os.makedirs(os.path.join(projects, n))
check(bridge("add_root", projects).get("ok"), "add_root")
check("error" in bridge("add_root", projects), "повтор той же папки — ошибка")
check("error" in bridge("add_root", os.path.join(TMP, "нет такой")), "несуществующая папка — ошибка")
d = bridge("projects")
names = sorted(i["name"] for i in d["items"] if not i["temp"])
check(names == ["bot", "сайт"], "проекты из папки в списке: " + ", ".join(names))
tag = d["kinds"][0]["tag"]
check(tag == "мои проекты", "группа названа по папке: " + tag)
r = bridge("check", tag, "новый")
check(r.get("path") and not r.get("problem"), "проверка имени нового проекта")
r = bridge("add", tag, "новый")
check(os.path.isdir(os.path.join(projects, "новый")), "новый проект заведён в папке")
r = bridge("add_temp", "")
check(r.get("path", "").startswith(HOME), "временный проект — в профиле: " + r.get("path", ""))
one = os.path.join(TMP, "отдельный")
os.makedirs(one)
check(bridge("add_extra", one).get("ok"), "add_extra")
check(any(i["path"] == one for i in bridge("projects")["items"]), "одна папка-проект в списке")
card = bridge("card", os.path.join(projects, "сайт"))
check("desc" in card, "карточка проекта читается")
check(bridge("remove_root", projects).get("ok") and bridge("remove_root", one).get("ok"), "remove_root")
check(os.path.isdir(projects), "убрать из списка — файлы на месте")
check([i for i in bridge("projects")["items"] if not i["temp"]] == [], "список снова пуст")

setup.uninstall()
check(not os.path.exists(os.path.join(DESK, setup.SHORTCUT)), "удаление: ярлык убран")
with open(os.path.join(HOME, ".claude", "settings.json"), encoding="utf-8") as h:
    check("statusLine" not in json.load(h), "удаление: статусная строка убрана")
print()
print("Всё прошло. Профиль:", TMP)
