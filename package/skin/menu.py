# -*- coding: utf-8 -*-
"""AIHUB — главное меню запуска: выбор проекта мышкой или с клавиатуры.

Показывается сразу после заставки и остаётся хозяином окна: выбрал проект —
внутри этого же окна запускается Claude Code, вышел из него — вернулся сюда же,
в список. Окно не закрывается и второй раз запускать ничего не надо.

Экран разбит на две колонки:
слева список проектов, справа карточка выбранного — описание из его CLAUDE.md,
когда была последняя сессия и о чём она была, плюс две кнопки. Кнопки нарисованы
на экране и кликаются мышкой: приёмов, о которых надо ЗНАТЬ, здесь нет.

Управление:
    стрелки / W и S   перебор списка
    Enter             новая сессия в выбранном проекте
    C                 продолжить последнюю сессию (claude --continue)
    1..9              быстрый выбор
    клик мышкой       по строке — выбрать, по кнопке — запустить
    колесо            прокрутка списка
    R                 перечитать список папок
    T                 сделать временным / постоянным (кнопка в карточке)
    Delete            удалить папку проекта (в Корзину, с вопросом в карточке)
    «+ добавить новый проект»  последняя строка ПОСТОЯННЫХ: в каком корне,
                      потом название — и папка заведена (см. add_project)
    «» разовая сессия» первая строка ВРЕМЕННЫХ: помощник без проекта, в домашней
                      папке, ничего не заводится (см. ONEOFF_PATH)
    «+ временный проект»  последняя строка списка: папка в TEMP_ROOT
                      по дате или со своим именем, и помощник сразу в ней
    клик по «Дождь на фоне»  включить или выключить анимацию заставки
    Q или Esc         выход

Список поделён на две группы, ПОСТОЯННЫЕ и ВРЕМЕННЫЕ.
Заголовки групп — не строки выбора: стрелки и колесо их
перескакивают, клик по ним ничего не делает (см. build_rows и step).

Кадр рисуется одной записью (см. Frame): без полной очистки, внутри
синхронизированного вывода. Раньше каждая стрелка начиналась с ESC[2J и
семью десятками отдельных записей — WezTerm успевал показать пустой
экран поверх фона, отсюда чёрные вспышки.

Буквенные клавиши работают в любой раскладке: С — это та же клавиша, что C,
и раскладку ради неё переключать не надо (см. LAYOUT ниже).

Мышь работает так: включаем режим SGR-репортов (ESC[?1000h и ESC[?1006h), и
терминал начинает слать координаты клика прямо в stdin. На Windows для этого
консоли нужно поднять флаг ENABLE_VIRTUAL_TERMINAL_INPUT, иначе клики до нас
не доходят вовсе.
"""
import ctypes
import glob
import json
import math
import msvcrt
import os
import re
import subprocess
import sys
import time
import console_guard
import crash_log
import session_store
import plans_link
import skin_settings
from texts import t

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SESSIONS_ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")

# Корни проектов, отдельные проекты и папка разовой сессии — свои у каждой
# машины, поэтому живут в settings.json (заводит install.py, см. README).
ROOTS = skin_settings.roots()                 # [(путь, метка)]
ACCENT_TAGS = skin_settings.accent_tags()     # метки, которые красятся жёлтым
SKIP = {"bat-backup", "node_modules"}

# Проекты вне корней: папка может называться одним, а работа в ней идти
# над другим. Имя — то, под которым проект знают; путь — настоящий, иначе
# сессии не найдутся.
EXTRA = skin_settings.extra()                 # [(путь, имя, метка)]

# Разовая сессия: помощник без проекта, новая папка не заводится.
# По умолчанию — домашняя папка: она есть всегда. ПРОДОЛЖИТЬ и ИСТОРИЯ
# работают как у проектов — по сессиям этой же папки.
ONEOFF_PATH = skin_settings.oneoff_path()

# Временные проекты — папки под разовую задачу: сделал, удалил. Всё, что
# лежит в TEMP_ROOT («temp_dir» в settings.json), временное всегда. Любой
# другой проект можно пометить временным кнопкой в карточке: пометки лежат
# в MARKS_FILE («marks_file») списком полных путей под ключом MARKS_KEY
# («marks_key»). Чужие ключи в этом файле меню не трогает, битый файл не
# перезаписывает.
TEMP_ROOT = skin_settings.temp_dir()
MARKS_FILE = skin_settings.marks_file()
MARKS_KEY = skin_settings.marks_key()

# Синхронизированный вывод (DEC 2026): терминал копит всё между этими двумя
# метками и показывает разом. WezTerm его понимает; кто не понимает — молча
# пропускает, и остаётся просто одна запись вместо семидесяти.
SYNC_ON = "\033[?2026h"
SYNC_OFF = "\033[?2026l"

# ── палитра ───────────────────────────────────────────────────────────────
# Одна на всю сборку: заставка, меню и всплывашка красятся этими же цветами.
BRIGHT = "\033[38;5;46m"     # основной зелёный
MID = "\033[38;5;40m"
DIM = "\033[38;5;28m"
FAINT = "\033[38;5;22m"
PALE = "\033[38;5;120m"
WHITE = "\033[38;5;231m"
WORK = "\033[38;5;220m"      # жёлтый акцент (#FFD200) — корни с "accent": true
SEL_BG = "\033[48;5;22m"
BTN_BG = "\033[48;5;28m"
R = "\033[0m"

# ── шапка ─────────────────────────────────────────────────────────────────
# Шрифт ANSI Shadow, шесть строк на букву. Ширина зашита в сами строки вместе
# с отбивкой справа, поэтому буквы склеиваются без разделителя.
LETTERS = {
    "C": [" ██████╗", "██╔════╝", "██║     ", "██║     ", "╚██████╗", " ╚═════╝"],
    "L": ["██╗     ", "██║     ", "██║     ", "██║     ", "███████╗", "╚══════╝"],
    "A": [" █████╗ ", "██╔══██╗", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "B": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔══██╗", "██████╔╝", "╚═════╝ "],
    "H": ["██╗  ██╗", "██║  ██║", "███████║", "██╔══██║", "██║  ██║", "╚═╝  ╚═╝"],
    "I": ["██╗  ", "██║  ", "██║  ", "██║  ", "██║  ", "╚═╝  "],
    "U": ["██╗   ██╗", "██║   ██║", "██║   ██║", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "D": ["██████╗ ", "██╔══██╗", "██║  ██║", "██║  ██║", "██████╔╝", "╚═════╝ "],
    "E": ["███████╗", "██╔════╝", "█████╗  ", "██╔══╝  ", "███████╗", "╚══════╝"],
    "G": [" ██████╗ ", "██╔════╝ ", "██║  ███╗", "██║   ██║", "╚██████╔╝", " ╚═════╝ "],
    "P": ["██████╗ ", "██╔══██╗", "██████╔╝", "██╔═══╝ ", "██║     ", "╚═╝     "],
    "T": ["████████╗", "╚══██╔══╝", "   ██║   ", "   ██║   ", "   ██║   ", "   ╚═╝   "],
    "M": ["███╗   ███╗", "████╗ ████║", "██╔████╔██║", "██║╚██╔╝██║", "██║ ╚═╝ ██║", "╚═╝     ╚═╝"],
    "N": ["███╗   ██╗", "████╗  ██║", "██╔██╗ ██║", "██║╚██╗██║", "██║ ╚████║", "╚═╝  ╚═══╝"],
    " ": ["   ", "   ", "   ", "   ", "   ", "   "],
}


def banner(word):
    rows = []
    for i in range(6):
        rows.append("".join(LETTERS[ch][i] for ch in word))
    return rows


# Шапка называет того, кто сейчас выбран: Tab переключает помощника —
# надпись меняется вместе с ним, и промахнуться с запуском невозможно.
BANNERS = {"claude": banner("CLAUDE"), "codex": banner("CHAT GPT")}

ENABLE_VIRTUAL_TERMINAL_INPUT = 0x0200
STD_INPUT_HANDLE = -10


def write(s):
    sys.stdout.write(s)
    sys.stdout.flush()


def at(row, col):
    return "\033[{};{}H".format(row, col)


def vislen(s):
    """Длина строки без учёта escape-последовательностей."""
    return len(re.sub(r"\033\[[0-9;]*[A-Za-z]", "", s))


def enable_vt_input():
    """Возвращает прежний режим консоли, чтобы восстановить его на выходе."""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        old = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(old)):
            return None
        kernel32.SetConsoleMode(handle, ENABLE_VIRTUAL_TERMINAL_INPUT)
        return old.value
    except Exception:
        return None


def restore_console(old):
    if old is None:
        return
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(STD_INPUT_HANDLE), old)
    except Exception:
        pass


# ── сбор данных о проектах ────────────────────────────────────────────────

def norm(path):
    """Путь для сравнения: регистр и косые черты Windows не различает."""
    return os.path.normcase(os.path.normpath(path))


def in_temp_root(path):
    return norm(os.path.dirname(path)) == norm(TEMP_ROOT)


def read_marks():
    """Содержимое MARKS_FILE. Файла нет — {}. Файл битый — ValueError.

    Битый файл не подменяется пустым: его может читать и другая программа, и
    переписать его «с нуля» значило бы стереть чужие данные.
    """
    try:
        with open(MARKS_FILE, encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise ValueError(error.strerror or str(error))
    if not isinstance(data, dict):
        raise ValueError(t("marks_not_dict"))
    return data


def temp_marks():
    try:
        paths = read_marks().get(MARKS_KEY)
    except ValueError:
        return []
    if not isinstance(paths, list):
        return []
    return [p for p in paths if isinstance(p, str)]


def set_temp_mark(path, temp):
    """Пометить проект временным (или снять пометку). → None или что не так."""
    try:
        data = read_marks()
    except ValueError as error:
        return t("marks_unreadable").format(os.path.basename(MARKS_FILE), error)
    paths = data.get(MARKS_KEY)
    paths = [p for p in paths if isinstance(p, str)] if isinstance(paths, list) else []
    paths = [p for p in paths if norm(p) != norm(path)]
    if temp:
        paths.append(path)
    data[MARKS_KEY] = paths
    try:
        os.makedirs(os.path.dirname(MARKS_FILE), exist_ok=True)
        spare = MARKS_FILE + ".tmp"
        with open(spare, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(spare, MARKS_FILE)
    except OSError as error:
        return t("marks_write_failed") + (error.strerror or str(error))
    return None


def birth(path):
    try:
        return os.path.getctime(path)
    except OSError:
        return 0.0


def collect_projects():
    """Все запускаемые записи. Порядок и группы расставляет build_rows."""
    marks = {norm(p) for p in temp_marks()}
    items = []
    for root, tag in ROOTS:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if not os.path.isdir(path) or name in SKIP or name.startswith("."):
                continue
            # Папка временных сама внутри корня — это не проект, её
            # содержимое и так показано в ВРЕМЕННЫХ.
            if norm(path) == norm(TEMP_ROOT):
                continue
            items.append({"name": name, "path": path, "tag": tag})
    seen = {norm(it["path"]) for it in items}
    for path, name, tag in EXTRA:
        if os.path.isdir(path) and norm(path) not in seen:
            items.append({"name": name, "path": path, "tag": tag})
            seen.add(norm(path))
    for it in items:
        if norm(it["path"]) in marks:
            it["temp"] = True
            it["born"] = birth(it["path"])
    # Папки из TEMP_ROOT временные всегда: пометка им не нужна и не снимается.
    if os.path.isdir(TEMP_ROOT):
        for name in os.listdir(TEMP_ROOT):
            path = os.path.join(TEMP_ROOT, name)
            if not os.path.isdir(path) or name.startswith(".") or norm(path) in seen:
                continue
            items.append({"name": name, "path": path, "tag": t("temp_tag"), "temp": True,
                          "fixed": True, "born": birth(path)})
            seen.add(norm(path))
    # Помеченные где-то ещё (пометку могла поставить и другая программа).
    for path in temp_marks():
        if os.path.isdir(path) and norm(path) not in seen and norm(path) != norm(ONEOFF_PATH):
            items.append({"name": os.path.basename(os.path.normpath(path)) or path,
                          "path": path, "tag": t("temp_tag"), "temp": True, "born": birth(path)})
            seen.add(norm(path))
    if os.path.isdir(ONEOFF_PATH):
        items.append({"name": t("oneoff_name"), "path": ONEOFF_PATH, "tag": t("oneoff_tag"),
                      "oneoff": True, "temp": True})
    return items


# ── строки списка ─────────────────────────────────────────────────────────
# Список на экране — это не просто проекты: две группы с заголовками и
# строки-действия. Каждая строка — словарь с полем kind:
#   header    заголовок группы, выбрать нельзя
#   item      проект (item) — номер num есть только у постоянных
#   add       «+ добавить новый проект» — последняя в ПОСТОЯННЫХ
#   add_temp  «+ временный проект» — последняя в списке

def build_rows(items):
    perm = [it for it in items if not it.get("temp")]
    oneoff = [it for it in items if it.get("oneoff")]
    temp = [it for it in items if it.get("temp") and not it.get("oneoff")]
    temp.sort(key=lambda it: it.get("born", 0.0), reverse=True)     # свежие сверху
    rows = [{"kind": "header", "title": t("group_perm"), "count": len(perm)}]
    for number, it in enumerate(perm, 1):
        rows.append({"kind": "item", "item": it, "num": number})
    rows.append({"kind": "add"})
    # Разовая — первой среди временных: это тоже «проекта нет», и она есть всегда.
    rows.append({"kind": "header", "title": t("group_temp"), "count": len(temp)})
    for it in oneoff + temp:
        rows.append({"kind": "item", "item": it, "num": None})
    rows.append({"kind": "add_temp"})
    return rows


def step(rows, selected, delta):
    """Сдвиг выбора на delta, заголовки групп перескакиваются, по кругу."""
    index = selected
    for _ in range(len(rows)):
        index = (index + delta) % len(rows)
        if rows[index]["kind"] != "header":
            return index
    return selected


def fix_selection(rows, selected):
    """Выбор после пересборки списка: в пределах и не на заголовке."""
    selected = max(0, min(selected, len(rows) - 1))
    if rows[selected]["kind"] == "header":
        return step(rows, selected, 1)
    return selected


def row_of(rows, path):
    for index, row in enumerate(rows):
        if row["kind"] == "item" and norm(row["item"]["path"]) == norm(path):
            return index
    return None


def row_kind(rows, kind):
    return next(i for i, row in enumerate(rows) if row["kind"] == kind)


def strip_md(line):
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)
    # Разметку снимаем посимвольно, а не парами: жирное часто открывается на
    # одной строке, а закрывается на следующей, и парный шаблон оставлял «**»
    # висеть прямо посреди описания.
    line = line.replace("**", "").replace("`", "")
    return line.strip()


def describe(path):
    """Первый осмысленный абзац из CLAUDE.md проекта (или README)."""
    for fn in ("CLAUDE.md", "README.md", "ГАЙД.md"):
        full = os.path.join(path, fn)
        if not os.path.isfile(full):
            continue
        try:
            text = open(full, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        para = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                if para:
                    break
                continue
            if line.startswith("#") or set(line) <= set("-=*_ "):
                continue
            if line.startswith(("|", ">", "```")):
                continue
            para.append(strip_md(line))
            if len(" ".join(para)) > 400:
                break
        if para:
            return " ".join(para), fn
    return t("no_description"), None


def session_slug(path):
    """Имя папки сессий: каждый не-латинский символ пути заменён дефисом.

    Так их называет сам Claude Code — видно по ~/.claude/projects.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def tail_lines(filename, limit=2000000):
    try:
        size = os.path.getsize(filename)
        with open(filename, "rb") as f:
            if size > limit:
                f.seek(size - limit)
                f.readline()          # обрезок строки в начале — выкинуть
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def message_text(entry):
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, dict) and chunk.get("type") == "text":
                parts.append(chunk.get("text", ""))
        return " ".join(parts)
    return ""


def last_session(path):
    """Когда была последняя сессия в проекте и о чём просили в конце."""
    folder = os.path.join(SESSIONS_ROOT, session_slug(path))
    files = glob.glob(os.path.join(folder, "*.jsonl"))
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    when = os.path.getmtime(newest)
    said = ""
    for line in reversed(tail_lines(newest)):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "user":
            continue
        text = message_text(entry)
        # Служебное вычищаем, а не отбрасываем строку целиком: настоящая просьба
        # часто приезжает вместе с напоминанием системы или обёрткой слэш-команды.
        text = re.sub(r"(?s)<system-reminder>.*?</system-reminder>", " ", text)
        text = re.sub(r"(?s)<command-(message|name)>.*?</command-\1>", " ", text)
        text = re.sub(r"(?s)</?command-args>", " ", text)
        text = re.sub(r"\[Image[^\]]*\]", " ", text)
        text = " ".join(text.split())
        if not text or text.startswith(("<", "Caveat:")):
            continue
        said = text
        break
    return {"when": when, "said": said, "file": newest}


def session_weight(session):
    """Во сколько токенов обойдётся продолжение — по последнему вызову сессии.

    Продолжение (`claude --resume`) заново отправляет весь накопленный
    разговор и заново пишет его в кэш, а потом тащит его в каждом ответе.
    По журналам возврат в долгую дневную сессию стоил 100 000+ токенов
    ещё до первого слова. Число должно стоять на кнопке —
    иначе разницы между «продолжить» и «начать заново» не видно вовсе.
    """
    if session.get("provider") != "claude":
        return None
    try:
        lines = tail_lines(session["file"], limit=400000)
    except OSError:
        return None
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        usage = (entry.get("message") or {}).get("usage")
        if not isinstance(usage, dict):
            continue
        total = (usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0) \
            + (usage.get("cache_creation_input_tokens") or 0)
        if total:
            return total
    return None


RUNNING = {"when": 0.0, "count": 0}


def running_sessions():
    """Сколько Claude Code уже работает. Лимит один на всех — они делят его.

    Считается по таблице процессов напрямую (console_guard уже умеет её
    снимать), без запуска tasklist: меню перерисовывается на каждую стрелку,
    и лишний процесс в этом цикле заметен на глаз. Ответ живёт пять секунд.
    """
    if time.time() - RUNNING["when"] < 5:
        return RUNNING["count"]
    try:
        table = console_guard.snapshot()
        count = sum(1 for _, (_, name) in table.items() if name == "claude.exe")
    except Exception:
        count = 0
    RUNNING["when"] = time.time()
    RUNNING["count"] = count
    return count


def human_when(stamp):
    now = time.time()
    day_now = time.strftime("%Y%m%d", time.localtime(now))
    day_was = time.strftime("%Y%m%d", time.localtime(stamp))
    clock = time.strftime("%H:%M", time.localtime(stamp))
    if day_now == day_was:
        return t("today_at") + clock
    if int(now - stamp) < 60 * 60 * 48:
        return t("yesterday_at") + clock
    return time.strftime(t("date_at"), time.localtime(stamp))


CARDS = {}
PROVIDER = "claude"


def card_data(item):
    if item["path"] not in CARDS:
        if item.get("oneoff"):
            text, source = t("oneoff_desc"), None
        else:
            text, source = describe(item["path"])
        CARDS[item["path"]] = {
            "desc": text,
            "source": source,
            "sessions": session_store.sessions(item["path"]),
        }
        history = CARDS[item["path"]]["sessions"]
        CARDS[item["path"]]["session"] = history[0] if history else None
    return CARDS[item["path"]]


# ── вращающийся куб ───────────────────────────────────────────────────────
# Проволочный куб рисуется точками в собственную сетку символов и печатается
# поверх карточки. Считается на лету, картинок не грузит.
CUBE_W, CUBE_H = 30, 13
SHADES = [FAINT, DIM, MID, BRIGHT]

CUBE_POINTS = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
CUBE_EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8)
              if sum(1 for i in range(3) if CUBE_POINTS[a][i] != CUBE_POINTS[b][i]) == 1]


def cube_frame(angle):
    """Возвращает CUBE_H строк с уже раскрашенным кубом."""
    grid = [[None] * CUBE_W for _ in range(CUBE_H)]
    sa, ca = math.sin(angle), math.cos(angle)
    sb, cb = math.sin(angle * 0.6), math.cos(angle * 0.6)

    def project(p):
        x, y, z = p
        x, z = x * ca - z * sa, x * sa + z * ca      # поворот вокруг Y
        y, z = y * cb - z * sb, y * sb + z * cb      # и вокруг X
        depth = z + 4.0
        k = 3.2 / depth
        # символ вдвое выше своей ширины, поэтому по горизонтали множитель больше
        return (CUBE_W / 2 + x * k * CUBE_W * 0.30,
                CUBE_H / 2 - y * k * CUBE_H * 0.42,
                depth)

    flat = [project(p) for p in CUBE_POINTS]
    for a, b in CUBE_EDGES:
        x1, y1, d1 = flat[a]
        x2, y2, d2 = flat[b]
        steps = int(max(abs(x2 - x1), abs(y2 - y1) * 2)) + 1
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x1 + (x2 - x1) * t))
            y = int(round(y1 + (y2 - y1) * t))
            d = d1 + (d2 - d1) * t
            if 0 <= x < CUBE_W and 0 <= y < CUBE_H:
                near = grid[y][x]
                if near is None or d < near:
                    grid[y][x] = d

    rows = []
    for line in grid:
        out = []
        prev = None
        for cell in line:
            if cell is None:
                if prev is not None:
                    out.append(R)
                    prev = None
                out.append(" ")
                continue
            level = min(3, max(0, int((5.0 - cell) * 1.6)))
            colour = SHADES[level]
            if colour != prev:
                out.append(colour)
                prev = colour
            out.append("█" if level >= 2 else ("▓" if level == 1 else "░"))
        out.append(R)
        rows.append("".join(out))
    return rows


# ── отрисовка ─────────────────────────────────────────────────────────────

def wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + (1 if cur else 0) <= width:
            cur = (cur + " " + word) if cur else word
        else:
            lines.append(cur)
            cur = word[:width]
    if cur:
        lines.append(cur)
    return lines


class Screen(object):
    """Куда кликать. Заполняется при отрисовке, читается при клике."""

    def __init__(self):
        self.rows = {}        # строка экрана -> индекс проекта
        self.buttons = []     # (строка, кол_от, кол_до, действие)
        self.cube_at = None   # (строка, колонка)
        self.cube_rows = 0    # сколько строк куба влезло в рамку карточки


# Размер окна, под который нарисован последний кадр. Полная очистка экрана
# (ESC[2J) нужна только когда он меняется: иначе каждый кадр и так
# переписывает все строки целиком.
SCREEN_SIZE = [None]


class Frame(object):
    """Кадр целиком: куски текста по строкам, выводятся ОДНОЙ записью.

    Почему так. Раньше draw() начиналась с ESC[2J и дальше писала кусками,
    каждый со своим flush — семьдесят записей на одну стрелку. WezTerm с
    четырёхслойным фоном успевал показать очищенный экран: чёрная вспышка
    на каждом движении по списку. Теперь очистки нет вовсе: каждая строка
    экрана переписывается поверх старой и дочищается ESC[K, всё ниже
    последней строки — ESC[J, и весь кадр идёт внутри синхронизированного
    вывода — терминал показывает его разом, уже готовым.
    """

    def __init__(self):
        self.parts = {}

    def put(self, row, col, text):
        self.parts.setdefault(row, []).append((col, text))

    def render(self, width, height, clear=False, tail=""):
        out = [SYNC_ON, "\033[2J" if clear else ""]
        last = max(self.parts) if self.parts else 0
        for row in range(1, last + 1):
            out.append(at(row, 1))
            pos = end = 1
            # sorted() устойчив: наложенное позже (куб поверх карточки)
            # остаётся позже и в выводе.
            for col, text in sorted(self.parts.get(row, []), key=lambda part: part[0]):
                if col > pos:
                    out.append(" " * (col - pos))
                elif col < pos:
                    out.append(at(row, col))
                out.append(text + R)
                pos = col + vislen(text)
                end = max(end, pos)
            if pos < end:
                out.append(at(row, end))
            # ESC[K на строке, дописанной до последней колонки, стёр бы её
            # последний знак: курсор в этот момент стоит на нём, а не за ним.
            if end <= width:
                out.append(R + "\033[K")
        # Всё ниже кадра — прочь. Кадр до самого низа окна — чистить нечего:
        # курсор ниже последней строки не встанет, и ESC[J стёр бы её саму.
        if last < height:
            out.append(at(last + 1, 1) + "\033[J")
        out.append(tail)
        out.append(SYNC_OFF)
        return "".join(out)


def show(frame, width, height, tail=""):
    """Вывести кадр. Очистка целиком — только при новом размере окна."""
    clear = SCREEN_SIZE[0] != (width, height)
    SCREEN_SIZE[0] = (width, height)
    write(frame.render(width, height, clear, tail))


def frame_top(title, width, colour):
    """Верх рамки с врезанным заголовком. width — вместе с боковинами."""
    label = " " + title + " "
    # Ширина считается вместе с обоими углами: «┌─» + надпись + хвост + «┐».
    # Раньше хвост был на знак короче, и верхняя планка не доходила до боковины.
    tail = max(0, width - 3 - len(label))
    return FAINT + "┌─" + R + colour + label + R + FAINT + "─" * tail + "┐" + R


def frame_bottom(width):
    return FAINT + "└" + "─" * max(0, width - 2) + "┘" + R


def frame_row(frame, row, x, width, content):
    """Строка внутри рамки: боковины на месте, содержимое добито пробелами."""
    inner = max(0, width - 2)
    pad = max(0, inner - vislen(content))
    frame.put(row, x, FAINT + "│" + R + content + " " * pad + FAINT + "│" + R)


def card_body(item, data, inner, text_w):
    """Содержимое карточки строками (уже раскрашенными) + строка кнопок."""
    tag_colour = colour_for_tag(item["tag"])
    lines = []
    lines.append(" " + tag_colour + item["name"].upper()[:text_w] + R)
    lines.append(" " + FAINT + item["path"][:text_w] + R)
    lines.append("")
    for line in wrap(data["desc"], text_w)[:7]:
        lines.append(" " + PALE + line + R)
    if data["source"]:
        lines.append(" " + FAINT + t("from_file") + data["source"] + R)
    lines.append("")

    session = data["session"]
    if session:
        lines.append(" " + DIM + session_store.LABELS[session["provider"]] + ": " + R + MID
                     + human_when(session["when"]) + R)
        if session["said"]:
            asked = wrap(t("asked_there") + session["said"] + " »", inner - 2)[:2]
            for line in asked:
                lines.append(" " + DIM + line + R)
        # Вес считается разбором хвоста стенограммы (до 400 КБ) — один раз
        # на карточку, а не на каждую стрелку: карточка живёт в CARDS.
        if "weight" not in data:
            data["weight"] = session_weight(session)
        weight = data["weight"]
        if weight:
            # Дорогое продолжение подсвечивается: 100k токенов в каждом ответе
            # съедают пятичасовой лимит за десяток вопросов.
            heavy = weight >= 60000
            colour = WORK if heavy else FAINT
            lines.append(" " + colour + t("tokens_per_reply").format(
                weight // 1000) + R)
            if heavy:
                lines.append(" " + FAINT + t("fresh_cheaper") + R)
    elif item.get("oneoff"):
        lines.append(" " + FAINT + t("no_oneoff_sessions") + R)
    else:
        lines.append(" " + FAINT + t("no_sessions") + R)
    lines.append("")
    return lines, session


def add_card_body(text_w):
    """Карточка для строки «+ добавить новый проект»: что будет и где."""
    lines = [" " + BRIGHT + t("new_project") + R, ""]
    for line in wrap(t("new_project_desc"), text_w):
        lines.append(" " + PALE + line + R)
    lines.append("")
    if not ROOTS:
        for line in wrap(t("no_roots"), text_w):
            lines.append(" " + WORK + line + R)
    for tag, label in kinds():
        lines.append(" " + kind_colour(tag) + "{:<8}".format(label.lower()) + R
                     + FAINT + ("→ " + root_for(tag))[:max(0, text_w - 8)] + R)
    lines.append("")
    return lines


def add_temp_card_body(text_w):
    """Карточка для строки «+ временный проект»."""
    lines = [" " + BRIGHT + t("temp_project") + R, " " + FAINT + TEMP_ROOT[:text_w] + R, ""]
    for line in wrap(t("temp_project_desc").format(temp_name_now()),
                     text_w):
        lines.append(" " + PALE + line + R)
    lines.append("")
    for line in wrap(t("temp_project_done"), text_w):
        lines.append(" " + DIM + line + R)
    lines.append("")
    return lines


def can_delete(item):
    """Можно ли предлагать «Удалить папку». → None или почему нельзя."""
    if item.get("oneoff"):
        return t("cant_home")
    path = norm(item["path"])
    keep = {norm(root) for root, _ in ROOTS} | {norm(TEMP_ROOT), norm(ONEOFF_PATH),
                                                norm(os.environ.get("USERPROFILE", ONEOFF_PATH))}
    if path in keep or norm(os.path.dirname(path)) == path:
        return t("cant_root")
    here = norm(HERE)
    if here == path or here.startswith(path.rstrip(os.sep) + os.sep):
        return t("cant_menu")
    # EXTRA — чужие папки: там может лежать целая игра, а не проект.
    if any(norm(extra) == path for extra, _, _ in EXTRA):
        return t("cant_extra")
    return None


def manage_lines(item, confirm, room):
    """Строки «временный / постоянный / удалить» под кнопками карточки.

    → список (строка, [(начало в строке, конец, действие)]) — колонки
    отсчитываются от левого края текста карточки, чтобы потом их сдвинуть.
    """
    out = []

    def buttons(labels):
        line, col, placed = " ", 1, []
        for text, action, style in labels:
            line += style + text + R + "   "
            placed.append((col, col + len(text) - 1, action))
            col += len(text) + 3
        return line, placed

    if confirm:
        if not item.get("temp"):
            # Постоянный проект — вопрос заметнее: какая именно папка и
            # сколько в ней, чтобы не удалить не то одним нажатием.
            out.append((" " + WORK + t("perm_delete_q")[:room] + R, []))
            path = item["path"]
            for i in range(0, len(path), max(1, room - 1))[:3]:
                out.append((" " + WHITE + path[i:i + room - 1] + R, []))
            size = confirm.get("size") if isinstance(confirm, dict) else None
            if size is not None:
                out.append((" " + PALE + t("size_is") + human_size(size) + R, []))
            out.append((" " + WORK + t("to_recycle")[:room] + R, []))
        else:
            out.append((" " + WORK + t("temp_delete_q1")[:room] + R, []))
            out.append((" " + WORK + t("temp_delete_q2") + R, []))
        out.append(buttons([(t("yes_delete"), "delete_yes", SEL_BG + WORK),
                            (t("cancel"), "delete_no", BTN_BG + WHITE)]))
        return out
    if item.get("temp"):
        labels = []
        if not item.get("fixed"):
            labels.append((t("make_perm"), "make_perm", SEL_BG + PALE))
        reason = can_delete(item)
        if not reason:
            labels.append((t("delete_folder"), "delete", SEL_BG + WORK))
        if labels:
            out.append(buttons(labels))
        if item.get("fixed"):
            text = t("always_temp") + TEMP_ROOT
            out.append((" " + FAINT + text[:room] + R, []))
        elif reason:
            out.append((" " + FAINT + (t("cant_delete_here") + reason)[:room] + R, []))
    else:
        # «Удалить папку» есть и у постоянных; вопрос у них заметнее —
        # см. ветку confirm выше.
        labels = [(t("make_temp"), "make_temp", SEL_BG + PALE)]
        reason = can_delete(item)
        if not reason:
            labels.append((t("delete_folder"), "delete", SEL_BG + WORK))
        out.append(buttons(labels))
        if reason:
            out.append((" " + FAINT + (t("cant_delete_here") + reason)[:room] + R, []))
    return out


def folder_size(path, budget=0.3):
    """Размер папки в байтах, если он считается быстро; иначе None.

    Большой проект (node_modules, сборки) обходится секундами — меню не
    должно замирать ради цифры, поэтому обход прерывается по времени.
    """
    total, deadline = 0, time.time() + budget
    try:
        for top, _dirs, files in os.walk(path):
            for name in files:
                try:
                    total += os.path.getsize(os.path.join(top, name))
                except OSError:
                    pass
            if time.time() > deadline:
                return None
    except OSError:
        return None
    return total


def human_size(size):
    units = t("size_units").split()
    for unit in units:
        if size < 1024 or unit == units[-1]:
            text = ("{:.0f}" if unit == units[0] or size >= 100 else "{:.1f}").format(size)
            return text.replace(".", t("decimal_sep")) + " " + unit
        size /= 1024.0


def list_row(row, selected_row):
    """Одна строка списка — готовое содержимое рамки (ширина 40)."""
    kind = row["kind"]
    if kind == "header":
        label = " {} · {} ".format(row["title"], row["count"])
        return FAINT + "─" + R + PALE + label + R + FAINT + "─" * max(0, 39 - len(label)) + R
    if kind in ("add", "add_temp"):
        text = t("add_row") if kind == "add" else t("add_temp_row")
        if selected_row:
            return "{}{}  + ▸ {:<34}{}".format(SEL_BG, WHITE, text, R)
        return "  {}+{}   {}{:<34}{}".format(BRIGHT, R, PALE, text, R)
    entry = row["item"]
    entry_colour = colour_for_tag(entry["tag"])
    name = entry["name"][:26]
    # Номер — только у постоянных (цифры 1..9 выбирают их). У разовой значок,
    # у временных пусто.
    if entry.get("oneoff"):
        mark = " »"
    elif row["num"]:
        mark = "{:>2}".format(row["num"])
    else:
        mark = "  "
    name_colour = PALE if entry.get("oneoff") else MID
    # У выбранной строки подложка тянется на всю ширину рамки: полоска
    # по длине текста выглядит как обрезанная, а не как выделение.
    if selected_row:
        return "{}{} {} ▸ {:<26} {}{:<7}{}".format(
            SEL_BG, WHITE, mark, name, entry_colour, entry["tag"], R)
    return " {}{}{}   {}{:<26}{} {}{:<7}{}".format(
        DIM, mark, R, name_colour, name, R, FAINT, entry["tag"], R)


def draw(rows, selected, width, height, angle=None, confirm=False, notice=""):
    """Весь экран меню одним кадром. angle — куб рисуется сразу в кадре.

    confirm — в карточке вопрос «удалить папку?» вместо обычных кнопок,
    notice — строка-сообщение внизу карточки (что не получилось).
    """
    scr = Screen()
    frame = Frame()

    title = BANNERS[PROVIDER]
    pad = max(2, (width - len(title[0])) // 2)
    for i, line in enumerate(title):
        frame.put(2 + i, pad, (MID if i % 2 == 0 else PALE) + line + R)

    sub = t("subtitle")
    frame.put(8, max(2, (width - len(sub)) // 2), DIM + sub + R)

    col = max(2, (width - 58) // 2)
    for provider, label in (("claude", "  Claude Code  "), ("codex", "  Codex  ")):
        colour = BTN_BG + WHITE if PROVIDER == provider else SEL_BG + DIM
        frame.put(9, col, colour + label + R)
        scr.buttons.append((9, col, col + len(label) - 1, "provider:" + provider))
        col += len(label) + 3
    frame.put(9, col, FAINT + t("tab_switch") + R)

    # ── строка настроек: фон и сколько помощников уже работает ───────────
    live = skin_settings.get("live_background")
    label = t("rain_button").format(t("rain_on") if live else t("rain_off"))
    bcol = max(2, (width - 58) // 2)
    frame.put(10, bcol, (BTN_BG + WHITE if live else SEL_BG + DIM) + label + R)
    scr.buttons.append((10, bcol, bcol + len(label) - 1, "background"))
    tail = bcol + len(label) + 2
    hint_bg = t("click_toggle")
    if tail + len(hint_bg) < width:
        frame.put(10, tail, FAINT + hint_bg + R)
        tail += len(hint_bg) + 4
    # Лимит у Claude один на все окна сразу, и внутри отдельного окна этого
    # не видно. Счётчик стоит здесь, рядом с кнопками запуска, а не в углу.
    already = running_sessions()
    if already >= 2:
        # Пропадать этой строке нельзя: это единственное место, где видно,
        # что лимит один на все открытые окна сразу. Поэтому не «влезло или
        # нет», а три длины на выбор — какая поместится в это окно.
        for warn in (t("running_long").format(already),
                     t("running_mid").format(already),
                     t("running_short").format(already)):
            if tail + len(warn) <= width:
                frame.put(10, tail, WORK + warn + R)
                break

    list_x = 4
    list_w = 42
    card_x = list_x + list_w + 3
    card_w = max(30, width - card_x - 3)
    top = 11
    # Куб живёт в правой части карточки, текст переносится по оставшемуся месту.
    room = card_w - 2 - 2
    with_cube = room > CUBE_W + 24
    text_w = (room - CUBE_W - 2) if with_cube else room

    current = rows[selected]
    kind = current["kind"]
    # Строки кнопок: (номер строки карточки, [(кол_от, кол_до, действие)]),
    # колонки — от левого края текста карточки (card_x + 1).
    button_lines = []
    if kind == "add":
        tag_colour = BRIGHT
        card_lines = add_card_body(text_w)
        labels = [(t("add_button"), "add")]
    elif kind == "add_temp":
        tag_colour = BRIGHT
        card_lines = add_temp_card_body(text_w)
        labels = [(t("create_and_run"), "add_temp")]
    else:
        item = current["item"]
        data = card_data(item)
        tag_colour = colour_for_tag(item["tag"])

        card_lines, session = card_body(item, data, card_w - 2, text_w)

        # Строка кнопок собирается отдельно: нужны их точные колонки для кликов.
        labels = [(t("run"), "run"),
                  (t("continue"), "continue")]
        if not session:
            labels[1] = (t("nothing_to_continue"), None)
        elif session["provider"] != PROVIDER:
            labels[1] = (t("take_over"), "continue")
    buttons_line = " "
    col = 1
    placed = []
    for text, action in labels:
        buttons_line += ((BTN_BG + WHITE) if action else FAINT) + text + R + "   "
        if action:
            placed.append((col, col + len(text) - 1, action))
        col += len(text) + 3
    button_lines.append((len(card_lines), placed))
    card_lines.append(buttons_line)

    if kind == "item":
        # «Планы» (TaskNotes) — задачи проекта. Кнопка — только если программа
        # установлена (узнаём по реестру, см. plans_link.py).
        history, plans = t("history_button"), t("plans_button")
        spots = [(1, len(history), "history")]
        line = " " + DIM + history + R
        if not item.get("oneoff") and plans_link.installed():
            col = 1 + len(history) + 3
            spots.append((col, col + len(plans) - 1, "plans"))
            line += "   " + BTN_BG + WHITE + plans + R
        card_lines.append(line)
        button_lines.append((len(card_lines) - 1, spots))
        if not item.get("oneoff"):
            card_lines.append("")
            for line, spots in manage_lines(item, confirm, card_w - 4):
                if spots:
                    button_lines.append((len(card_lines), spots))
                card_lines.append(line)
    if notice:
        card_lines.append("")
        for line in wrap(notice, card_w - 4)[:2]:
            card_lines.append(" " + WORK + line + R)

    body_h = max(len(rows), len(card_lines))
    body_h = min(body_h, max(3, height - top - 4))
    bottom = top + 1 + body_h

    # ── список ────────────────────────────────────────────────────────────
    frame.put(top, list_x, frame_top(t("projects"), list_w, BRIGHT))
    offset = max(0, selected - body_h + 1)
    for i in range(body_h):
        row = top + 1 + i
        index = offset + i
        if index >= len(rows):
            frame_row(frame, row, list_x, list_w, "")
            continue
        # Заголовок группы в scr.rows не попадает: клик по нему — мимо.
        if rows[index]["kind"] != "header":
            scr.rows[row] = index
        frame_row(frame, row, list_x, list_w, list_row(rows[index], index == selected))
    frame.put(bottom, list_x, frame_bottom(list_w))

    # ── карточка ──────────────────────────────────────────────────────────
    frame.put(top, card_x, frame_top(t("card"), card_w, tag_colour))
    for i in range(body_h):
        frame_row(frame, top + 1 + i, card_x, card_w,
                  card_lines[i] if i < len(card_lines) else "")
    frame.put(bottom, card_x, frame_bottom(card_w))

    for index, spots in button_lines:
        if index < body_h:
            for c1, c2, action in spots:
                scr.buttons.append((top + 1 + index, card_x + c1 + 1, card_x + c2 + 1, action))

    if with_cube:
        scr.cube_at = (top + 1, card_x + card_w - CUBE_W - 2)
        scr.cube_rows = min(CUBE_H, body_h)
        if angle is not None:
            # Куб — в этом же кадре: иначе карточка на миг рисовалась пустой
            # под ним, и он мигал на каждой стрелке.
            row0, col0 = scr.cube_at
            for i, line in enumerate(cube_frame(angle)[:scr.cube_rows]):
                frame.put(row0 + i, col0, line)

    hint = t("hint")
    hint_row = min(height - 1, bottom + 2)
    frame.put(hint_row, max(2, (width - len(hint)) // 2), FAINT + hint + R)
    extra = t("hint_tab")
    if hint_row + 1 < height:
        frame.put(hint_row + 1, max(2, (width - len(extra)) // 2), FAINT + extra + R)
    show(frame, width, height)
    return scr


def draw_cube(scr, angle):
    """Следующий кадр куба — одной записью, внутри синхронизированного вывода.

    Строки куба одной ширины (CUBE_W) и всегда на одном месте, поэтому
    новый кадр целиком закрывает старый и мусора не остаётся.
    """
    if not scr.cube_at:
        return
    row0, col0 = scr.cube_at
    parts = [SYNC_ON]
    for i, line in enumerate(cube_frame(angle)[:scr.cube_rows]):
        parts.append(at(row0 + i, col0) + line)
    parts.append(SYNC_OFF)
    write("".join(parts))


# ── ввод ──────────────────────────────────────────────────────────────────

# Русская раскладка — та же физическая клавиша. Переключаться туда-обратно
# ради одной буквы — приём, о котором надо ЗНАТЬ; вместо этого меню принимает
# обе раскладки: С работает как C, Ц как W, Ы как S, К как R, Й как Q.
LAYOUT = {
    "й": b"q", "ц": b"w", "ы": b"s", "с": b"c", "к": b"r",
    "р": b"h", "е": b"t",
}


def console_encoding():
    """Кодировка ввода консоли — спрашиваем её, а не угадываем.

    Гадать по одному байту нельзя в принципе: 0xE1 — это «б» в cp1251 и «с»
    в cp866, и перебор кодировок подряд превращал половину алфавита в чужие
    команды. `claude-menu.cmd` ставит chcp 65001, но код обязан работать и
    в консоли с 866. Нет консоли (запустили из редактора) — None.
    """
    try:
        code_page = ctypes.windll.kernel32.GetConsoleCP()
    except Exception:
        return None
    if not code_page:
        return None
    return "utf-8" if code_page == 65001 else "cp%d" % code_page


def read_letter(first):
    """Не-ASCII байт с клавиатуры → латинская буква на той же клавише.

    При chcp 65001 msvcrt.getch() отдаёт русскую букву кусками UTF-8, по байту
    за вызов, поэтому хвост последовательности дочитываем здесь же. В консоли
    с однобайтовой кодовой страницей буква приходит одним байтом и читается
    ею же. Незнакомая буква — b"" (событие просто игнорируется).
    """
    encoding = console_encoding()
    if encoding and encoding != "utf-8":
        try:
            return LAYOUT.get(first.decode(encoding).lower(), b"")
        except (UnicodeDecodeError, LookupError):
            return b""

    lead = first[0]
    tail_len = 1 if 0xC0 <= lead <= 0xDF else 2 if 0xE0 <= lead <= 0xEF else 0
    buf = first
    for _ in range(tail_len):
        if not msvcrt.kbhit():
            break
        nxt = msvcrt.getch()
        if not 0x80 <= nxt[0] <= 0xBF:      # не хвост UTF-8, а следующая клавиша
            try:
                msvcrt.ungetch(nxt)
            except OSError:
                pass
            break
        buf += nxt

    if len(buf) > 1:
        # Хвост дочитался — перед нами последовательность UTF-8, и она
        # окончательна: однобайтовые кодировки после неё пробовать НЕЛЬЗЯ.
        # Ведущий байт русской буквы (0xD0/0xD1) в cp1251 сам по себе —
        # «Р»/«С», поэтому «э», «ю», «я» и вся вторая половина алфавита
        # читались как «с», то есть как ПРОДОЛЖИТЬ: нажатие любой из них
        # запускало сессию. Обожглись 07.09.2026.
        try:
            return LAYOUT.get(buf.decode("utf-8").lower(), b"")
        except UnicodeDecodeError:
            return b""
    # Одинокий байт при неизвестной кодовой странице: cp1251 распространённее
    # cp866 в раскладках, но угадывать всё равно нечем — берём одну и молчим,
    # если не сошлось. Перебирать вторую нельзя, см. console_encoding().
    try:
        return LAYOUT.get(buf.decode("cp1251").lower(), b"")
    except UnicodeDecodeError:
        return b""


def read_event():
    """('key', b'..') или ('click', строка, колонка) или ('wheel', +1/-1)."""
    ch = msvcrt.getch()
    if ch >= b"\x80":
        return ("key", read_letter(ch))
    if ch != b"\x1b":
        return ("key", ch)
    if not msvcrt.kbhit():
        return ("key", b"\x1b")
    seq = msvcrt.getch()
    if seq != b"[":
        return ("key", seq)

    body = b""
    while True:
        c = msvcrt.getch()
        body += c
        if c.isalpha() or c == b"~":
            break
        if len(body) > 32:
            break

    if body.startswith(b"<"):
        # ESC[<кнопка;колонка;строкаM — M нажали, m отпустили
        try:
            button, col, row = body[1:-1].split(b";")
            button, col, row = int(button), int(col), int(row)
        except (ValueError, IndexError):
            return ("key", b"")
        if button in (64, 65):
            return ("wheel", -1 if button == 64 else 1)
        if body.endswith(b"M") and button == 0:
            return ("click", row, col)
        return ("key", b"")

    if body in (b"A", b"D"):
        return ("key", b"UP")
    if body in (b"B", b"C"):
        return ("key", b"DOWN")
    if body == b"3~":
        return ("key", b"DEL")
    return ("key", b"")


# ── запуск ────────────────────────────────────────────────────────────────

def choose_session(item):
    history = session_store.sessions(item["path"])
    selected = 0
    if not history:
        return None
    while True:
        width, height = os.get_terminal_size()
        page = max(1, height - 7)
        offset = max(0, selected - page + 1)
        # Кадр целиком, без ESC[2J: тот же приём, что в draw() — см. Frame.
        frame = Frame()
        frame.put(1, 1, BRIGHT + t("history_title") + item["name"] + R)
        frame.put(3, 1, DIM + t("history_selected") + session_store.LABELS[PROVIDER]
                  + t("history_hint").rstrip("\n") + R)
        for i, entry in enumerate(history[offset:offset + page], offset):
            label = "{} {} — {}".format(session_store.LABELS[entry["provider"]], human_when(entry["when"]), entry.get("said", "").replace("\n", " "))
            frame.put(5 + i - offset, 1, (SEL_BG + WHITE if i == selected else MID)
                      + "  " + label[:max(1, width - 5)] + R)
        show(frame, width, height)
        event = read_event()
        if event[0] == "click":
            index = offset + event[1] - 5
            if 0 <= index < len(history) and event[1] < 5 + page:
                return history[index]
        elif event[0] == "wheel":
            selected = (selected + event[1]) % len(history)
        elif event[0] == "key":
            key = event[1].lower()
            if key in (b"\x1b", b"q"):
                return None
            if key in (b"up", b"w"):
                selected = (selected - 1) % len(history)
            elif key in (b"down", b"s"):
                selected = (selected + 1) % len(history)
            elif key in (b"\r", b"\n"):
                return history[selected]


# ── новый проект ──────────────────────────────────────────────────────────
# Последняя строка ПОСТОЯННЫХ. Два шага: сначала корень (если их больше
# одного), потом название. Папка заводится в корне из ROOTS с той же меткой,
# и меню сразу встаёт на неё — дальше обычный ЗАПУСТИТЬ.

def kinds():
    """[(метка, надпись на кнопке)] — по одному на корень из настроек."""
    return [(tag, tag.upper()) for _, tag in ROOTS]


BAD_CHARS = '<>:"/\\|?*'
RESERVED = ({"CON", "PRN", "AUX", "NUL"} | {"COM%d" % i for i in range(1, 10)}
            | {"LPT%d" % i for i in range(1, 10)})
NAME_MAX = 60


def root_for(tag):
    for root, root_tag in ROOTS:
        if root_tag == tag:
            return root
    return None


def colour_for_tag(tag):
    return WORK if tag in ACCENT_TAGS else BRIGHT


kind_colour = colour_for_tag


def check_name(name, root):
    """Название → (имя папки, что с ним не так). Всё в порядке — второе None.

    Пустое имя ошибкой не считается: просто создавать ещё нечего.
    """
    # Хвостовые точки и пробелы Windows отрезает у папки молча — отрезаем
    # сами, чтобы в предпросмотре стояло ровно то имя, что получится.
    clean = name.strip().rstrip(". ")
    if not clean:
        return clean, None
    for ch in clean:
        if ch in BAD_CHARS or ord(ch) < 32:
            return clean, t("bad_char").format(ch)
    if clean.startswith("."):
        return clean, t("dot_name")
    if clean.split(".")[0].strip().upper() in RESERVED:
        return clean, t("reserved_name")
    if clean.lower() in SKIP:
        return clean, t("skipped_name")
    if os.path.exists(os.path.join(root, clean)):
        return clean, t("exists")
    return clean, None


def dialog_box(frame, title, colour, lines, width, height):
    """Рамка посреди экрана. Возвращает (левая колонка, первая строка текста)."""
    box_w = min(76, width - 4)
    left = max(2, (width - box_w) // 2)
    top = max(2, (height - len(lines) - 4) // 2)
    frame.put(top, left, frame_top(title, box_w, colour))
    for i, line in enumerate(lines):
        frame_row(frame, top + 1 + i, left, box_w, line)
    frame.put(top + 1 + len(lines), left, frame_bottom(box_w))
    return left, top + 1, box_w


def read_mouse_tail(getc):
    """Хвост ESC[… после ESC уже прочитан. → ('click', строка, колонка) или None."""
    body = ""
    while True:
        c = getc()
        body += c
        if c.isalpha() or c == "~" or len(body) > 32:
            break
    if not body.startswith("<") or not body.endswith("M"):
        return None
    try:
        button, col, row = (int(x) for x in body[1:-1].split(";"))
    except ValueError:
        return None
    return ("click", row, col) if button == 0 else None


def ask_kind(selected):
    """Шаг первый: в каком корне. → метка из ROOTS или None (назад)."""
    KINDS = kinds()
    while True:
        width, height = os.get_terminal_size()
        box_w = min(76, width - 4)
        lines = ["", "  " + PALE + t("which_root") + R, ""]
        rows = []
        for i, (tag, label) in enumerate(KINDS):
            button = "  {}  {:<9}".format(i + 1, label)
            style = (BTN_BG + WHITE) if i == selected else (SEL_BG + DIM)
            # Путь режется по рамке: длинный корень иначе выдавливает боковину.
            tail = (t("folder_in") + root_for(tag))[:max(0, box_w - 8 - len(button))]
            rows.append(len(lines))
            lines.append("  " + style + button + R + "   " + kind_colour(tag) + tail + R)
            lines.append("")
        frame = Frame()
        left, first, _ = dialog_box(frame, t("new_project"), BRIGHT, lines, width, height)
        hint = t("kind_hint")
        frame.put(first + len(lines) + 2, max(2, (width - len(hint)) // 2), FAINT + hint + R)
        show(frame, width, height)

        event = read_event()
        if event[0] == "click":
            for i, index in enumerate(rows):
                if event[1] == first + index and left < event[2] < left + box_w - 1:
                    return KINDS[i][0]
        elif event[0] == "wheel":
            selected = (selected + event[1]) % len(KINDS)
        elif event[0] == "key":
            key = event[1].lower()
            if key in (b"\x1b", b"q", b"\x03"):
                return None
            if key in (b"up", b"w"):
                selected = (selected - 1) % len(KINDS)
            elif key in (b"down", b"s"):
                selected = (selected + 1) % len(KINDS)
            elif key.isdigit() and 1 <= int(key) <= len(KINDS):
                return KINDS[int(key) - 1][0]
            elif key in (b"\r", b"\n"):
                return KINDS[selected][0]


def ask_name(tag, root=None, title=None, fallback=None):
    """Шаг второй: название. → путь заведённой папки или None (назад).

    Ввод читается getwch(), а не getch(): кириллица приходит сразу буквой,
    а не кусками UTF-8, и LAYOUT здесь ни при чём — тут буквы и нужны.
    Запрещённые в имени папки символы не вставляются вовсе, а под полем
    пишется, почему: иначе «ничего не произошло» и непонятно, что не так.

    Для временного проекта (tag None) передаются root, title и fallback —
    имя по дате: поле можно оставить пустым, и папка назовётся им.
    """
    root = root or root_for(tag)
    colour = kind_colour(tag) if tag else PALE
    title = title or (t("new_project_title") + dict(kinds())[tag])
    create = t("create_and_run") if fallback else t("create")
    back = t("back")
    hint = t("temp_name_hint") if fallback else t("name_hint")
    name = ""
    notice = ""
    try:
        while True:
            width, height = os.get_terminal_size()
            box_w = min(76, width - 4)
            field_w = box_w - 8
            clean, error = check_name(name, root)
            by_date = fallback and not clean
            if by_date:
                clean = unique_name(root, fallback)
            ready = bool(clean) and not error

            shown = name[-(field_w - 2):]
            lines = ["", "  " + PALE + t("project_name") + R,
                     "  " + SEL_BG + WHITE + " " + shown + " " * (field_w - 1 - len(shown)) + R, ""]
            # Предпросмотр всегда в две строки: высота рамки прыгать не должна.
            preview = t("folder_colon") + os.path.join(root, clean) if clean else t("folder_will_be_in") + root
            parts = [preview[i:i + box_w - 6] for i in range(0, len(preview), box_w - 6)][:2]
            for part in parts + [""] * (2 - len(parts)):
                lines.append("  " + (FAINT if not clean else PALE) + part + R)
            # Сначала то, что мешает создать папку, и только потом рассказ
            # о пропущенной букве: иначе «уже есть» прячется за старым словом.
            if by_date:
                idle = t("by_date_idle")
            else:
                idle = "" if clean else t("type_a_name")
            message = error or notice or idle
            lines.append("  " + ((WORK if (notice or error) else FAINT) + message[:box_w - 6] + R))
            lines.append("")
            buttons_index = len(lines)
            lines.append("  " + ((BTN_BG + WHITE) if ready else FAINT) + create + R
                         + "   " + SEL_BG + DIM + back + R)
            lines.append("")

            # Кадр одной записью: на каждую букву рамка пишется поверх самой
            # себя, экран чистится только при смене размера окна (см. show).
            frame = Frame()
            left, first, box_w = dialog_box(frame, title, colour, lines, width, height)
            frame.put(first + len(lines) + 2, max(2, (width - len(hint)) // 2), FAINT + hint + R)
            # Настоящий мигающий курсор в поле: так видно, что сюда печатать.
            show(frame, width, height,
                 tail=at(first + 2, left + 4 + len(shown)) + "\033[?25h")

            # Сообщение под полем держится, пока не сотрут букву:
            # если гасить его на следующей же клавише, при быстром наборе
            # «символ нельзя» мелькнёт и пропадёт, а имя молча окажется другим.
            ch = msvcrt.getwch()
            click = None
            if ch == "\x1b":
                if msvcrt.kbhit() and msvcrt.getwch() == "[":
                    click = read_mouse_tail(msvcrt.getwch)
                    if not click:
                        continue
                else:
                    return None
            if click:
                row, col = click[1], click[2]
                bcol = left + 3
                if row == first + buttons_index:
                    if bcol <= col < bcol + len(create):
                        ch = "\r"
                    elif bcol + len(create) + 3 <= col < bcol + len(create) + 3 + len(back):
                        return None
                if ch != "\r":
                    continue
            if ch in ("\x00", "\xe0"):
                msvcrt.getwch()                  # вторая половина служебной клавиши
            elif ch == "\x03":
                return None
            elif ch in ("\r", "\n"):
                if ready:
                    path = os.path.join(root, clean)
                    try:
                        os.makedirs(path)
                        # Файл задач «Планов» — не вышло, проект всё равно заведён
                        plans_link.seed(path)
                        return path
                    except OSError as problem:
                        notice = t("failed") + (problem.strerror or str(problem))
            elif ch in ("\x08", "\x7f"):
                name = name[:-1]
                notice = ""
            elif ch == "\x17":                   # Ctrl+Backspace — слово целиком
                name = name.rstrip()
                name = name[:len(name) - len(name.split(" ")[-1])]
                notice = ""
            elif ch in BAD_CHARS:
                notice = t("bad_char_skipped").format(ch)
            elif ord(ch) < 32 or "\ud800" <= ch <= "\udfff":
                pass
            elif len(name) >= NAME_MAX:
                notice = t("too_long").format(NAME_MAX)
            else:
                name += ch
    finally:
        write("\033[?25l")


def add_project():
    """Оба шага подряд. «Назад» со второго возвращает к первому.

    Корень один — спрашивать не о чем, сразу название; Esc тогда — в список.
    """
    KINDS = kinds()
    if not KINDS:
        return None
    selected = 0
    while True:
        tag = KINDS[0][0] if len(KINDS) == 1 else ask_kind(selected)
        if tag is None:
            return None
        selected = [tag_ for tag_, _ in KINDS].index(tag)
        path = ask_name(tag)
        if path or len(KINDS) == 1:
            return path


# ── временный проект ──────────────────────────────────────────────────────
# Последняя строка списка. Один шаг: имя (пустое — по дате), и помощник
# сразу запускается в новой папке. Корень TEMP_ROOT заводится сам, если его
# ещё нет: makedirs создаёт и промежуточные папки.

def temp_name_now():
    # Двоеточие в имени папки Windows не пускает, поэтому «2140», а не «21:40».
    return time.strftime("%Y-%m-%d %H%M")


def unique_name(root, name):
    """Имя по дате, которое ещё свободно: два временных за минуту — « (2)»."""
    candidate, number = name, 2
    while os.path.exists(os.path.join(root, candidate)) and number < 100:
        candidate = "{} ({})".format(name, number)
        number += 1
    return candidate


def add_temp():
    return ask_name(None, root=TEMP_ROOT, title=t("temp_project"), fallback=temp_name_now())


def refreshed(selected, path=None):
    """Пересобрать список и встать на path (или остаться около прежнего места)."""
    rows = build_rows(collect_projects())
    if path:
        index = row_of(rows, path)
        if index is not None:
            return rows, index
    return rows, fix_selection(rows, selected)


def recycle(path):
    """Папку — в Корзину, а не насовсем. → None или что не так.

    Путь идёт в PowerShell через переменную окружения, а не вклеивается в
    текст команды и не дописывается аргументом: у -Command хвостовые
    аргументы склеиваются с кодом в одну строку, и путь с пробелом или
    кавычкой стал бы кодом. Кириллица в окружении доезжает целой — это
    Unicode-блок процесса, консольная кодовая страница его не трогает.
    """
    script = ("Add-Type -AssemblyName Microsoft.VisualBasic; "
              "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory("
              "$env:AIHUB_RECYCLE, 'OnlyErrorDialogs', 'SendToRecycleBin')")
    env = os.environ.copy()
    env["AIHUB_RECYCLE"] = path
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                                 "-ExecutionPolicy", "Bypass", "-Command", script],
                                env=env, capture_output=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as error:
        return t("not_deleted") + str(error)
    if os.path.exists(path):
        why = result.stderr.decode("oem", errors="replace").strip().splitlines()
        return (t("not_deleted_busy")
                + (why[0][:120] if why else ""))
    return None


def run_project(item, resume, session=None):
    # Очистка и первая строка — одной записью: между ними экран не должен
    # успеть показаться пустым. Дальше launch_agent.py сразу печатает
    # «Проверяю соединение…», пока скрипт прокси думает (до нескольких секунд).
    what = t("continuing") if resume else t("launching")
    write("\033[?1006l\033[?1000l\033[?25h" + R + "\033[2J\033[H"
          + "{}▓▒░ {} {}{}{} ░▒▓{}\n\n".format(DIM, what, BRIGHT, item["name"], DIM, R))
    args = [sys.executable, os.path.join(HERE, "launch_agent.py"), PROVIDER, item["path"]]
    if resume:
        session = session or card_data(item)["session"]
        if session:
            args.extend(["--session", session["provider"] + ":" + session["id"]])
    try:
        subprocess.call(args)
    except OSError as error:
        write("\n" + str(error) + "\n")
    CARDS.pop(item["path"], None)          # сессия только что была — карточку пересобрать
    write(t("session_closed")
          .format(DIM, R))
    msvcrt.getch()
    # После сессии экран чужой (и мог прокрутиться) — следующий кадр с очисткой.
    SCREEN_SIZE[0] = None
    write("\033[?25l\033[?1000h\033[?1006h")


def main():
    global PROVIDER
    # Вкладку закрыли — уходим сразу, не держа псевдоконсоль
    # (см. console_guard.py: без этого висло всё окно WezTerm).
    console_guard.watch()
    # Записать, где лежит меню, — «Планы» найдут AIHUB по реестру (plans_link.py)
    plans_link.register_skin()
    old_mode = enable_vt_input()
    write("\033]0;AIHUB\007")
    write("\033[?25l\033[?1000h\033[?1006h")   # курсор прочь, мышь на приём
    rows = build_rows(collect_projects())
    selected = fix_selection(rows, 0)
    scr = None
    dirty = True
    angle = 0.0
    size = (0, 0)
    confirm = False       # в карточке висит вопрос «удалить папку?»
    notice = ""           # что не получилось — строкой внизу карточки

    def current_item():
        return rows[selected].get("item")

    try:
        while True:
            now_size = os.get_terminal_size()
            if (now_size.columns, now_size.lines) != size:
                size = (now_size.columns, now_size.lines)
                dirty = True
            angle += 0.09
            if dirty:
                scr = draw(rows, selected, size[0], size[1], angle=angle,
                           confirm=confirm, notice=notice)
                dirty = False
            else:
                draw_cube(scr, angle)

            if not msvcrt.kbhit():
                time.sleep(0.05)
                continue

            event = read_event()
            kind = event[0]
            dirty = True
            notice = ""
            item = current_item()
            row_kind_now = rows[selected]["kind"]

            # Вопрос «удалить?» отвечается только своими кнопками, Enter и
            # Esc. Любое другое действие снимает вопрос и выполняется как
            # обычно — кроме Esc и Q: они здесь значат «отмена», а не «выход».
            action = None
            if kind == "click":
                row, col = event[1], event[2]
                for brow, c1, c2, act in scr.buttons:
                    if row == brow and c1 <= col <= c2:
                        action = act
                        break
                if action is None and row in scr.rows:
                    selected = scr.rows[row]
                    # Строки-действия по клику сразу делают своё, а не только
                    # подсвечиваются, как строка проекта.
                    if rows[selected]["kind"] in ("add", "add_temp"):
                        action = rows[selected]["kind"]
                    confirm = False
                if action is None:
                    confirm = False
                    continue
            elif kind == "wheel":
                confirm = False
                selected = step(rows, selected, event[1])
                continue
            else:
                value = event[1]
                if confirm:
                    confirm = False
                    if value in (b"\r", b"\n"):
                        action = "delete_yes"
                    else:
                        continue
                elif value == b"\t":
                    PROVIDER = "codex" if PROVIDER == "claude" else "claude"
                    continue
                elif value in (b"UP", b"w", b"W"):
                    selected = step(rows, selected, -1)
                    continue
                elif value in (b"DOWN", b"s", b"S"):
                    selected = step(rows, selected, 1)
                    continue
                elif value in (b"\r", b"\n"):
                    action = {"add": "add", "add_temp": "add_temp"}.get(row_kind_now, "run")
                elif value in (b"c", b"C"):
                    if item and card_data(item)["session"]:
                        action = "continue"
                elif value in (b"h", b"H"):
                    action = "history" if item else None
                elif value in (b"p", b"P"):
                    action = "plans" if item and not item.get("oneoff") and plans_link.installed() else None
                elif value in (b"t", b"T"):
                    if item and not item.get("oneoff") and not item.get("fixed"):
                        action = "make_perm" if item.get("temp") else "make_temp"
                elif value == b"DEL":
                    if item and not item.get("oneoff"):
                        action = "delete"
                elif value in (b"r", b"R"):
                    CARDS.clear()
                    rows = build_rows(collect_projects())
                    selected = fix_selection(rows, 0)
                    continue
                elif value in (b"q", b"Q", b"\x1b", b"\x03"):
                    return
                elif value.isdigit():
                    # Цифры — только постоянным: у временных номера нет.
                    for index, row in enumerate(rows):
                        if row.get("num") == int(value):
                            selected = index
                    continue
                if action is None:
                    continue

            item = current_item()
            if action != "delete":
                confirm = False
            if action == "background":
                # WezTerm перечитает конфигурацию сам: skin_settings
                # трогает .wezterm.lua следом за записью настройки.
                skin_settings.toggle("live_background")
            elif action.startswith("provider:"):
                PROVIDER = action.split(":", 1)[1]
            elif action == "history" and item:
                session = choose_session(item)
                if session:
                    run_project(item, True, session)
            elif action == "plans" and item:
                notice = plans_link.open_plans(item["path"]) or t("plans_opening")
            elif action == "add":
                path = add_project()
                if path:
                    rows, selected = refreshed(selected, path)
            elif action == "add_temp":
                path = add_temp()
                if path:
                    rows, selected = refreshed(selected, path)
                    run_project(rows[selected]["item"], False)
            elif action in ("make_temp", "make_perm") and item:
                notice = set_temp_mark(item["path"], action == "make_temp") or ""
                rows, selected = refreshed(selected, item["path"])
            elif action == "delete" and item:
                reason = can_delete(item)
                if reason:
                    notice = t("cant_delete") + reason
                else:
                    # Размер считается один раз, при вопросе, а не на каждом кадре.
                    confirm = {"size": folder_size(item["path"])}
            elif action == "delete_yes" and item and not can_delete(item):
                draw(rows, selected, size[0], size[1], angle=angle,
                     notice=t("recycling"))
                notice = recycle(item["path"]) or ""
                if not notice:
                    set_temp_mark(item["path"], False)     # пометка больше ни к чему
                    CARDS.pop(item["path"], None)
                rows, selected = refreshed(selected)
            elif action == "delete_no":
                pass
            elif action in ("run", "continue") and item:
                run_project(item, action == "continue")
    finally:
        write("\033[?1006l\033[?1000l\033[?25h" + R + "\033[2J\033[H")
        restore_console(old_mode)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # finally в main() чистит экран целиком, поэтому пишем после
        # него и держим строку до нажатия клавиши.
        write("\n" + crash_log.write("меню", error) + "\n")
        msvcrt.getch()
