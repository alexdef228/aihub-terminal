# -*- coding: utf-8 -*-
"""Живая статусная строка Claude Code «Matrix».

Две строки:
    ▓▒░ путь ░ git ветка ░ модель ░ усилие ░▒▓
    5ч [▓▓▓░░░░░] 23% до 18:00 · 2ч 14м ░ 7дн [▓▓▓▓░░░░] 41% до 12.09 18:00 · 4д 3ч

Нижняя строка — только расход лимитов и время до сброса. Контекст и стоимость
сессии убраны намеренно.

Анимация: в settings.json стоит refreshInterval = 1, поэтому скрипт запускается
раз в секунду даже когда сессия простаивает — по полосам бежит светлая искра,
а обратный отсчёт тикает.

Поля JSON описаны в code.claude.com/docs/en/statusline. Блок rate_limits
приходит только у подписок Pro и Max и только после первого ответа модели,
поэтому его отсутствие обрабатывается отдельно.
"""
import json
import os
import subprocess
import sys
import time

from ui_lang import pick

# Python на Windows печатает в консоль в системной ANSI-кодировке, и кириллица
# приезжает кракозябрами. Переключаем поток явно.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BRIGHT = "\033[38;5;46m"
MID = "\033[38;5;40m"
DIM = "\033[38;5;28m"
PALE = "\033[38;5;120m"
SPARK = "\033[38;5;231m"
WARN = "\033[38;5;208m"
ALERT = "\033[38;5;196m"
R = "\033[0m"

BAR_WIDTH = 10


# Строка перерисовывается раз в секунду (refreshInterval = 1), и каждый
# запуск — отдельный процесс. Спрашивать git по 3600 раз в час ради ветки,
# которая меняется раз в день, незачем: ответ живёт в файле рядом 15 секунд.
BRANCH_CACHE = os.path.join(os.environ.get("TEMP", "."), "statusline-branch.json")


def git_branch(path):
    try:
        with open(BRANCH_CACHE, encoding="utf-8") as handle:
            cached = json.load(handle)
        if cached.get("path") == path and time.time() - cached.get("when", 0) < 15:
            return cached.get("branch")
    except Exception:
        pass
    branch = None
    try:
        out = subprocess.run(
            ["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=1,
        )
        if out.returncode == 0:
            branch = out.stdout.strip()
    except Exception:
        pass
    try:
        with open(BRANCH_CACHE, "w", encoding="utf-8") as handle:
            json.dump({"path": path, "branch": branch, "when": time.time()}, handle)
    except Exception:
        pass
    return branch


def context_size(transcript):
    """Сколько токенов уезжает на сервер в каждом ответе этой сессии.

    Это главное число расхода, и до сих пор его не было видно нигде.
    Замерено 09.09.2026 по журналам: сессии доходили до 745 000 и 918 000
    токенов, и каждый вызов инструмента тащил их целиком. Считается по
    последней записи о расходе в файле сессии — хвоста в четверть мегабайта
    хватает, целиком файл читать не нужно (они бывают по 11 МБ).
    """
    if not transcript or not os.path.isfile(transcript):
        return None
    try:
        with open(transcript, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 262144))
            tail = handle.read().split(b"\n")
    except OSError:
        return None
    for line in reversed(tail):
        if b'"usage"' not in line:
            continue
        try:
            usage = (json.loads(line.decode("utf-8", "replace")).get("message") or {}).get("usage")
        except ValueError:
            continue
        if not isinstance(usage, dict):
            continue
        total = ((usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                 + (usage.get("cache_creation_input_tokens") or 0))
        if total:
            return total
    return None


def short_path(path):
    home = os.path.expanduser("~")
    if path.lower().startswith(home.lower()):
        path = "~" + path[len(home):]
    parts = path.replace("\\", "/").rstrip("/").split("/")
    if len(parts) > 3:
        parts = ["…"] + parts[-2:]
    return "/".join(parts)


def level_color(pct):
    if pct >= 80:
        return ALERT
    if pct >= 50:
        return WARN
    return BRIGHT


def bar(pct, tick):
    """Полоса расхода с бегущей искрой — она и делает строку живой."""
    filled = int(round(BAR_WIDTH * min(pct, 100) / 100.0))
    spark = tick % BAR_WIDTH
    color = level_color(pct)
    cells = []
    for i in range(BAR_WIDTH):
        if i == spark:
            cells.append(SPARK + "▓" + R)
        elif i < filled:
            cells.append(color + "█" + R)
        else:
            cells.append(DIM + "░" + R)
    return "{}[{}{}{}]{}".format(DIM, R, "".join(cells), DIM, R)


def until(ts):
    """«2ч 14м» или «4д 3ч» — сколько осталось до сброса окна."""
    left = int(ts - time.time())
    if left <= 0:
        return pick("вот-вот", "any moment")
    days, rem = divmod(left, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return pick("{}д {}ч", "{}d {}h").format(days, hours)
    if hours:
        return pick("{}ч {:02d}м", "{}h {:02d}m").format(hours, minutes)
    return pick("{}м", "{}m").format(minutes)


def reset_at(ts, with_date):
    stamp = time.localtime(ts)
    return time.strftime("%d.%m %H:%M" if with_date else "%H:%M", stamp)


def window(label, data, tick, with_date):
    """Один блок лимита: подпись, полоса, процент, время сброса и остаток."""
    pct = data.get("used_percentage")
    if pct is None:
        return None
    color = level_color(pct)
    text = "{}{}{} {} {}{:.0f}%{}".format(PALE, label, R, bar(pct, tick), color, pct, R)
    ts = data.get("resets_at")
    if ts:
        text += pick(" {}до {} · {}{}", " {}resets {} · {}{}").format(DIM, reset_at(ts, with_date), until(ts), R)
    return text


# AIHUB Терминал рисует лимиты и контекст в своём окне, а узнать их может
# только отсюда: rate_limits Claude Code отдаёт одной статусной строке. Поэтому
# строка заодно кладёт снимок в файл — по файлу на вкладку (метку AIHUB_TAB
# ставит терминал), вне терминала — по файлу на сессию. Запись через временный
# файл: окно читает папку раз в две секунды и не должно поймать недописанный JSON.
STATUS_DIR = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "AIHUB", "status")


def share_status(data, cwd, model, effort, limits, size):
    tab = os.environ.get("AIHUB_TAB")
    key = "tab-" + tab if tab else "session-" + str(data.get("session_id") or "unknown")
    path = os.path.join(STATUS_DIR, key + ".json")
    # limits_at — когда цифры лимитов в последний раз ПОМЕНЯЛИСЬ: строка
    # перерисовывается постоянно и отдаёт последние известные лимиты, хоть
    # часовой давности, поэтому время файла для этого не годится.
    limits_at = time.time()
    try:
        with open(path, encoding="utf-8") as handle:
            old = json.load(handle)
        if (old.get("rate_limits") or None) == (limits or None):
            limits_at = old.get("limits_at") or 0
    except (OSError, ValueError):
        pass
    snapshot = {
        "tab": tab,
        "session_id": data.get("session_id"),
        "cwd": cwd,
        "model": model,
        "effort": effort,
        "context": size,
        "rate_limits": limits or None,
        "limits_at": limits_at,
        "cost": (data.get("cost") or {}).get("total_cost_usd"),
        "when": time.time(),
    }
    try:
        os.makedirs(STATUS_DIR, exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as handle:
            json.dump(snapshot, handle, ensure_ascii=False)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    workspace = data.get("workspace") or {}
    cwd = workspace.get("current_dir") or data.get("cwd") or os.getcwd()
    model = (data.get("model") or {}).get("display_name") or "claude"
    effort = (data.get("effort") or {}).get("level")
    limits = data.get("rate_limits") or {}

    tick = int(time.time())
    sep = "{} ░ {}".format(DIM, R)

    # ── первая строка: где мы и чем работаем ──────────────────────────────
    top = ["{}{}{}".format(BRIGHT, short_path(cwd), R)]
    branch = git_branch(cwd)
    if branch:
        top.append("{}git{} {}{}{}".format(PALE, R, MID, branch, R))
    top.append("{}{}{}".format(MID, model, R))
    if effort:
        top.append("{}{}{}".format(DIM, effort, R))
    if data.get("fast_mode"):
        top.append("{}fast{}".format(PALE, R))

    sys.stdout.write("{}▓▒░{} {} {}░▒▓{}\n".format(DIM, R, sep.join(top), DIM, R))

    # ── вторая строка: расход лимитов, всегда ─────────────────────────────
    bottom = []
    five = window(pick("5ч", "5h"), limits.get("five_hour") or {}, tick, with_date=False)
    seven = window(pick("7дн", "7d"), limits.get("seven_day") or {}, tick, with_date=True)
    spend = window(pick("счёт", "spend"), limits.get("spend_limit") or {}, tick, with_date=True)

    for part in (five, seven, spend):
        if part:
            bottom.append(part)

    if not bottom:
        # Блок приходит только у Pro/Max и только после первого ответа модели.
        bottom.append(pick("{}лимиты: данных пока нет{}", "{}limits: no data yet{}").format(DIM, R))

    # Размер контекста — рядом с лимитами, потому что тратит их именно он.
    size = context_size(data.get("transcript_path"))
    share_status(data, cwd, model, effort, limits, size)
    if size:
        thousands = size // 1000
        if thousands >= 200:
            bottom.append(pick("{}контекст {}k ▲ пора /compact{}", "{}context {}k ▲ time to /compact{}").format(ALERT, thousands, R))
        elif thousands >= 120:
            bottom.append(pick("{}контекст {}k ▲ дорого{}", "{}context {}k ▲ expensive{}").format(WARN, thousands, R))
        else:
            bottom.append(pick("{}контекст {}k{}", "{}context {}k{}").format(DIM, thousands, R))

    bottom.append("{}{}{}".format(DIM, time.strftime("%H:%M:%S"), R))
    sys.stdout.write(sep.join(bottom))


if __name__ == "__main__":
    main()
