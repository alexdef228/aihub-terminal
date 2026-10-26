# -*- coding: utf-8 -*-
"""Строки интерфейса на двух языках: русский и английский.

Язык берётся из настроек («language»: "ru" или "en"). Не задан — по языку
Windows: русская система — русский, любая другая — английский.

    from texts import t
    t("run")                      → "  ЗАПУСТИТЬ  (Enter)  " / "  RUN  (Enter)  "
    t("tokens_per_reply").format(49)

Новая строка интерфейса — сюда, парой; в коде только t("ключ").
Пробелы по краям — часть надписи: ими кнопки выравниваются по ширине.
"""
import ctypes

import skin_settings

TEXTS = {
    # ── меню: шапка и строка настроек ────────────────────────────────────
    "subtitle": ("AIHUB ░ общие проекты и память ░ Tab — сменить помощника",
                 "AIHUB ░ shared projects and memory ░ Tab — switch assistant"),
    "tab_switch": ("Tab — переключить", "Tab — switch"),
    "rain_button": ("  Дождь на фоне: {}  ", "  Background rain: {}  "),
    "rain_on": ("идёт", "on"),
    "rain_off": ("замер", "off"),
    "click_toggle": ("клик — переключить", "click — toggle"),
    "running_long": ("уже работает {} сессии Claude — лимит на всех общий",
                     "{} Claude sessions already running — the limit is shared"),
    "running_mid": ("{} сессии Claude — лимит общий", "{} Claude sessions — shared limit"),
    "running_short": ("сессий: {}", "sessions: {}"),

    # ── меню: список и карточка ──────────────────────────────────────────
    "projects": ("ПРОЕКТЫ", "PROJECTS"),
    "card": ("КАРТОЧКА", "CARD"),
    "add_row": ("добавить новый проект", "add a new project"),
    "oneoff_name": ("разовая сессия", "one-off session"),
    "oneoff_tag": ("разово", "one-off"),
    "oneoff_desc": ("Без проекта: новая папка не заводится, помощник запускается "
                    "в папке выше. Для быстрого вопроса или разового скрипта. "
                    "ПРОДОЛЖИТЬ поднимает последнюю разовую.",
                    "No project: no folder is created, the assistant starts in the "
                    "folder above. For a quick question or a throwaway script. "
                    "CONTINUE resumes the last one-off session."),
    "no_description": ("Описания нет: в папке проекта не нашлось CLAUDE.md или README.md.",
                       "No description: the project folder has no CLAUDE.md or README.md."),
    "from_file": ("— из ", "— from "),
    "asked_there": ("на ней просили: « ", "asked there: « "),
    "tokens_per_reply": ("продолжить — это {}k токенов в каждом ответе",
                         "continuing costs {}k tokens in every reply"),
    "fresh_cheaper": ("новая сессия дешевле: старое подхватит /comeon",
                      "a new session is cheaper: /comeon picks up the past"),
    "no_oneoff_sessions": ("разовых сессий ещё не было", "no one-off sessions yet"),
    "no_sessions": ("сессий в этом проекте ещё не было", "no sessions in this project yet"),
    "today_at": ("сегодня в ", "today at "),
    "yesterday_at": ("вчера в ", "yesterday at "),
    "date_at": ("%d.%m в %H:%M", "%d.%m at %H:%M"),
    "run": ("  ЗАПУСТИТЬ  (Enter)  ", "  RUN  (Enter)  "),
    "continue": ("  ПРОДОЛЖИТЬ  (C)  ", "  CONTINUE  (C)  "),
    "nothing_to_continue": ("  нечего продолжать  ", "  nothing to continue  "),
    "take_over": ("  ПЕРЕНЯТЬ  (C)  ", "  TAKE OVER  (C)  "),
    "history_button": ("  ИСТОРИЯ ОБОИХ  (H)  ", "  HISTORY  (H)  "),
    # «Планы» (TaskNotes) — отдельная программа; кнопка — только если стоит
    "plans_button": ("  ЗАДАЧИ В «ПЛАНАХ»  (P)  ", "  TASKS IN TASKNOTES  (P)  "),
    "plans_opening": ("открываю «Планы» на этом проекте…", "opening TaskNotes on this project…"),
    "plans_missing": ("программа «Планы» не установлена", "TaskNotes is not installed"),
    "plans_failed": ("«Планы» не открылись: ", "TaskNotes did not open: "),
    "plans_seed_failed": ("файл задач не завёлся: ", "the task file was not created: "),
    "add_button": ("  ДОБАВИТЬ ПРОЕКТ  (Enter)  ", "  ADD PROJECT  (Enter)  "),
    "hint": ("клик по строке — выбрать ░ клик по кнопке — запустить ░ "
             "Tab — помощник ░ H — история ░ R — обновить ░ Q — выход",
             "click a row — select ░ click a button — run ░ "
             "Tab — assistant ░ H — history ░ R — rescan ░ Q — quit"),
    "hint_tab": ("Ctrl+Shift+P — открыть ещё один проект вкладкой рядом, не выходя отсюда",
                 "Ctrl+Shift+P — open another project in a tab next to this one"),

    # ── карточка «новый проект» ──────────────────────────────────────────
    "new_project": ("НОВЫЙ ПРОЕКТ", "NEW PROJECT"),
    "new_project_title": ("НОВЫЙ ПРОЕКТ ░ ", "NEW PROJECT ░ "),
    "new_project_desc": ("Заведёт папку под новый проект в одном из корней "
                         "и сразу покажет его в списке.",
                         "Creates a folder for a new project in one of the roots "
                         "and shows it in the list right away."),
    "no_roots": ("Корней проектов пока нет: впиши папку в «roots» "
                 "в settings.json или перезапусти install.py.",
                 "No project roots yet: add a folder to «roots» in "
                 "settings.json or run install.py again."),

    # ── постоянные и временные ───────────────────────────────────────────
    "group_perm": ("ПОСТОЯННЫЕ", "PERMANENT"),
    "group_temp": ("ВРЕМЕННЫЕ", "TEMPORARY"),
    "temp_tag": ("врем.", "temp"),
    "add_temp_row": ("временный проект", "temporary project"),
    "temp_project": ("ВРЕМЕННЫЙ ПРОЕКТ", "TEMPORARY PROJECT"),
    "temp_project_desc": ("Папка под разовую задачу. Имя — по дате и времени, например «{}», "
                          "или своё. Помощник запускается в ней сразу.",
                          "A folder for a one-off task. Named by date and time, e.g. «{}», "
                          "or by you. The assistant starts in it right away."),
    "temp_project_done": ("Задача сделана — кнопка «Удалить папку» в карточке проекта "
                          "отправит её в Корзину.",
                          "Task done? The «Delete folder» button in the project card "
                          "sends it to the Recycle Bin."),
    "create_and_run": ("  СОЗДАТЬ И ЗАПУСТИТЬ  (Enter)  ", "  CREATE AND RUN  (Enter)  "),
    "temp_name_hint": ("Enter — создать и запустить ░ Esc — назад в список",
                       "Enter — create and run ░ Esc — back to the list"),
    "by_date_idle": ("пусто — назову по дате и времени; можно вписать своё",
                     "empty — it will be named by date and time; or type a name"),
    "make_temp": ("  СДЕЛАТЬ ВРЕМЕННЫМ  (T)  ", "  MAKE TEMPORARY  (T)  "),
    "make_perm": ("  СДЕЛАТЬ ПОСТОЯННЫМ  (T)  ", "  MAKE PERMANENT  (T)  "),
    "always_temp": ("временный всегда: лежит в ", "always temporary: it lives in "),
    "marks_not_dict": ("внутри не словарь", "not a JSON object inside"),
    "marks_unreadable": ("{} не читается ({}) — пометку не записал",
                         "{} can't be read ({}) — the mark was not saved"),
    "marks_write_failed": ("не записал пометку: ", "could not save the mark: "),

    # ── удаление папки ───────────────────────────────────────────────────
    "delete_folder": ("  УДАЛИТЬ ПАПКУ  (Del)  ", "  DELETE FOLDER  (Del)  "),
    "yes_delete": ("  ДА, УДАЛИТЬ  (Enter)  ", "  YES, DELETE  (Enter)  "),
    "cancel": ("  ОТМЕНА  (Esc)  ", "  CANCEL  (Esc)  "),
    "perm_delete_q": ("ПОСТОЯННЫЙ ПРОЕКТ — удалить папку целиком?",
                      "PERMANENT PROJECT — delete the whole folder?"),
    "size_is": ("в ней ", "size: "),
    "to_recycle": ("Уйдёт в Корзину, вернуть можно оттуда.",
                   "It goes to the Recycle Bin; restore it from there."),
    "temp_delete_q1": ("Удалить папку со всем, что в ней? Уйдёт в Корзину,",
                       "Delete the folder with everything in it? It goes"),
    "temp_delete_q2": ("вернуть можно оттуда.", "to the Recycle Bin; restore it from there."),
    "cant_home": ("это домашняя папка", "this is the home folder"),
    "cant_root": ("это корневая папка — меню её не удаляет",
                  "this is a root folder — the menu won't delete it"),
    "cant_menu": ("в этой папке живёт само меню", "the menu itself lives in this folder"),
    "cant_extra": ("это папка вне корней проектов (например, игра) — только через Проводник",
                   "this folder is outside the project roots (a game, say) — use Explorer"),
    "cant_delete_here": ("удалить отсюда нельзя: ", "can't delete from here: "),
    "cant_delete": ("удалить нельзя: ", "can't delete: "),
    "recycling": ("переношу папку в Корзину…", "moving the folder to the Recycle Bin…"),
    "not_deleted": ("не удалилось: ", "not deleted: "),
    "not_deleted_busy": ("не удалилось — возможно, в папке открыта сессия или файл. ",
                         "not deleted — a session or a file may be open in the folder. "),
    "size_units": ("байт КБ МБ ГБ", "B KB MB GB"),
    "decimal_sep": (",", "."),

    # ── история ──────────────────────────────────────────────────────────
    "history_title": ("  ОБЩАЯ ИСТОРИЯ — ", "  SHARED HISTORY — "),
    "history_selected": ("  Выбрано: ", "  Selected: "),
    "history_hint": (" ░ Enter / клик — продолжить или перенять ░ Esc — назад\n\n",
                     " ░ Enter / click — continue or take over ░ Esc — back\n\n"),

    # ── новый проект: шаги ───────────────────────────────────────────────
    "which_root": ("Какой это проект?", "What kind of project is it?"),
    "folder_in": ("папка в ", "folder in "),
    "kind_hint": ("стрелки или цифра — выбрать ░ Enter или клик — дальше ░ Esc — назад",
                  "arrows or a digit — choose ░ Enter or click — next ░ Esc — back"),
    "project_name": ("Название проекта:", "Project name:"),
    "folder_colon": ("папка: ", "folder: "),
    "folder_will_be_in": ("папка появится в ", "the folder will appear in "),
    "type_a_name": ("впиши название — например, «Сайт для клиента»",
                    "type a name — for example, «client-website»"),
    "create": ("  СОЗДАТЬ  (Enter)  ", "  CREATE  (Enter)  "),
    "back": ("  НАЗАД  (Esc)  ", "  BACK  (Esc)  "),
    "name_hint": ("Enter — создать ░ Esc — назад, к выбору корня",
                  "Enter — create ░ Esc — back to choosing a root"),
    "failed": ("не вышло: ", "failed: "),
    "bad_char": ("символ «{}» в имени папки нельзя", "«{}» is not allowed in a folder name"),
    "bad_char_skipped": ("символ «{}» в имени папки нельзя — пропустил",
                         "«{}» is not allowed in a folder name — skipped"),
    "dot_name": ("папки с точкой в начале меню прячет — в списке её не будет",
                 "the menu hides folders starting with a dot — it won't be listed"),
    "reserved_name": ("такое имя Windows занимает под устройство",
                      "Windows reserves this name for a device"),
    "skipped_name": ("папки с таким именем меню пропускает",
                     "the menu skips folders with this name"),
    "exists": ("такой проект уже есть — он в списке", "this project already exists — it's in the list"),
    "too_long": ("длиннее {} знаков название не бывает", "a name can't be longer than {} characters"),

    # ── запуск ───────────────────────────────────────────────────────────
    "continuing": ("продолжаю", "continuing"),
    "launching": ("запускаю", "launching"),
    "session_closed": ("\n{}сессия закрыта ░ нажми любую клавишу — вернёшься в список проектов{}\n",
                       "\n{}session closed ░ press any key to return to the project list{}\n"),
    "checking_connection": ("░ Проверяю соединение…", "░ Checking the connection…"),
    "handoff_unreadable": ("Переписку для передачи прочитать не удалось",
                           "Could not read the conversation to hand over"),
    "handoff_codex": ("Продолжи работу по сохранённой переписке: {}. Это исторический "
                      "контекст. Прочитай файл и MEMORY.md проекта, проверь состояние "
                      "файлов перед продолжением.",
                      "Continue the work from the saved conversation: {}. It is historical "
                      "context. Read the file and the project's MEMORY.md, check the state "
                      "of the files before continuing."),
    "handoff_claude": ("Продолжи работу по сохранённой переписке: {}. Прочитай этот файл "
                       "и MEMORY.md проекта. Проверь состояние файлов перед продолжением.",
                       "Continue the work from the saved conversation: {}. Read this file "
                       "and the project's MEMORY.md. Check the state of the files before "
                       "continuing."),
    "md_session": ("Сессия: ", "Session: "),
    "md_updated": ("Обновлена: ", "Updated: "),
    "md_user": ("Владелец", "User"),
    "md_image": ("[Изображение: ", "[Image: "),
    "md_image_origin": ("в исходной сессии", "in the original session"),
    "md_memory": ("# Общая память проекта\n\nПоследняя сохранённая переписка: [{stem}.md]({stem}.md)"
                  "\n\nПроект: {project}\n\nДругие сессии сохранены рядом в Markdown. "
                  "Это переписка, а не проверенный отчёт о выполнении.\n",
                  "# Shared project memory\n\nLast saved conversation: [{stem}.md]({stem}.md)"
                  "\n\nProject: {project}\n\nOther sessions are saved next to it as Markdown. "
                  "This is a conversation, not a verified report of what was done.\n"),
    "unknown_assistant":("Неизвестный помощник: ", "Unknown assistant: "),
    "claude_missing": ("Claude Code не найден. Установка: npm i -g @anthropic-ai/claude-code",
                       "Claude Code not found. Install: npm i -g @anthropic-ai/claude-code"),
    "codex_missing": ("Codex CLI не найден. Установка: npm i -g @openai/codex",
                      "Codex CLI not found. Install: npm i -g @openai/codex"),
    "project_missing": ("Папка проекта не найдена: ", "Project folder not found: "),
    "session_gone": ("Выбранная сессия больше не найдена. Обнови список.",
                     "The selected session is gone. Refresh the list."),
    "launch_error": ("\nОшибка запуска: ", "\nLaunch error: "),
    "launch_crashed": ("\nЗапуск сорвался: ", "\nLaunch crashed: "),
}


def detect():
    """Язык по настройке, а без неё — по языку интерфейса Windows."""
    try:
        chosen = skin_settings.get("language")
    except Exception:
        chosen = None
    if chosen in ("ru", "en"):
        return chosen
    try:
        # Младшие 10 бит LANGID — основной язык; 0x19 — русский.
        return "ru" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x19 else "en"
    except Exception:
        return "en"


LANG = detect()


def t(key):
    ru, en = TEXTS[key]
    return ru if LANG == "ru" else en
