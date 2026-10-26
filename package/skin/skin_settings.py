# -*- coding: utf-8 -*-
"""Настройки сборки: что переключается из меню и что своё у каждой машины.

Зачем отдельный файл. `wezterm.lua` — код, и просить человека лезть туда
ради одной галочки неправильно. Настройки лежат в `settings.json` рядом:
меню пишет, `wezterm.lua` читает при каждой загрузке конфигурации. Файл
заводит `install.py`; нет его — работают значения по умолчанию ниже.

Что в нём:
    language         "en" / "ru"; пусто — по языку Windows
    live_background  анимированный дождь на фоне (кнопка в меню)
    roots            папки, где лежат проекты: [{path, label, accent}]
                     accent — подсветить такие проекты жёлтым (например, рабочие)
    extra            проекты вне корней: [{path, name, label}]
    oneoff_dir       где запускать «разовую сессию» без проекта
    temp_dir         папка временных проектов: всё в ней — во «ВРЕМЕННЫХ»
    marks_file       где хранить пометки «этот проект временный» (json)
    marks_key        ключ списка путей в marks_file
    proxy_script     необязательно: .ps1, который печатает адрес прокси
                     последней строкой (http://…); пусто — окружение как есть

В путях работают `~` и `%ПЕРЕМЕННЫЕ%`.

Первые версии писали `настройки.json` с русскими ключами (язык, корни,
путь…). Такой файл по-прежнему читается: ключи переводятся на лету, а
при первой записи из меню настройки уходят в `settings.json`.

Про «пинок». WezTerm перечитывает конфигурацию сам, но следит он за
`.wezterm.lua`, а не за нашим json — про него он ничего не знает. Поэтому
после записи настройки файл конфигурации переписывается теми же байтами:
меняется время правки, WezTerm видит это и перечитывает всё, уже с новым
значением. Окно при этом не моргает и вкладки не теряются.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, 'settings.json')
LEGACY_FILE = os.path.join(HERE, 'настройки.json')
HOME = os.path.expanduser('~')
WEZTERM = os.path.join(HOME, '.wezterm.lua')

# Живой фон по умолчанию выключен: анимированный GIF на 60 кадров в
# четырёхслойном фоне перерисовывается постоянно, даже когда в консоли
# ничего не происходит, и на слабых видеокартах WezTerm от этого падал.
DEFAULTS = {
    'language': '',
    'live_background': False,
    'roots': [{'path': os.path.join('~', 'Projects'), 'label': 'projects', 'accent': False}],
    'extra': [],
    'oneoff_dir': '~',
    'temp_dir': os.path.join('~', 'TempProjects'),
    'marks_file': os.path.join('~', '.claude', 'aihub-projects.json'),
    'marks_key': 'temporary',
    'proxy_script': '',
}

# Старые русские ключи → нынешние английские.
LEGACY_KEYS = {
    'язык': 'language', 'живой_фон': 'live_background', 'корни': 'roots',
    'отдельные': 'extra', 'разовая_папка': 'oneoff_dir', 'прокси_скрипт': 'proxy_script',
}
LEGACY_ITEM_KEYS = {'путь': 'path', 'метка': 'label', 'акцент': 'accent', 'имя': 'name'}


def normalize(values):
    """Русские ключи старых настроек → английские; английский ключ важнее."""
    out = {}
    for key, value in values.items():
        new = LEGACY_KEYS.get(key, key)
        if new in ('roots', 'extra') and isinstance(value, list):
            value = [{LEGACY_ITEM_KEYS.get(k, k): v for k, v in item.items()}
                     if isinstance(item, dict) else item for item in value]
        if new == key or new not in values:
            out[new] = value
    return out


def expand(path):
    return os.path.normpath(os.path.expandvars(os.path.expanduser(path or '')))


def stored():
    """То, что записано на диске (settings.json, иначе старый настройки.json)."""
    for path in (FILE, LEGACY_FILE):
        try:
            with io.open(path, encoding='utf-8') as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return normalize(data)
        except (OSError, ValueError):
            continue
    return {}


def read():
    """Все настройки. Файла нет или он битый — значения по умолчанию."""
    values = json.loads(json.dumps(DEFAULTS))
    data = stored()
    for key in DEFAULTS:
        if key in data:
            values[key] = data[key]
    return values


def get(key):
    return read()[LEGACY_KEYS.get(key, key)]


def roots():
    """[(путь, метка)] — корни проектов, пути уже раскрыты."""
    return [(expand(r.get('path')), r.get('label') or 'projects')
            for r in get('roots') if isinstance(r, dict) and r.get('path')]


def accent_tags():
    """Метки, которые красятся акцентом (жёлтым), а не зелёным."""
    return {r.get('label') for r in get('roots') if isinstance(r, dict) and r.get('accent')}


def extra():
    """[(путь, имя в списке, метка)] — проекты вне корней."""
    return [(expand(e['path']), e.get('name') or os.path.basename(expand(e['path'])),
             e.get('label') or 'projects')
            for e in get('extra') if isinstance(e, dict) and e.get('path')]


def oneoff_path():
    return expand(get('oneoff_dir') or '~')


def temp_dir():
    """Папка временных проектов; создаётся меню при первом временном."""
    return expand(get('temp_dir') or DEFAULTS['temp_dir'])


def marks_file():
    return expand(get('marks_file') or DEFAULTS['marks_file'])


def marks_key():
    return get('marks_key') or DEFAULTS['marks_key']


def proxy_script():
    script = get('proxy_script')
    return expand(script) if script else ''


def write(values):
    with io.open(FILE, 'w', encoding='utf-8') as handle:
        json.dump(normalize(values), handle, ensure_ascii=False, indent=2)


def set(key, value):
    """Записать настройку и попросить WezTerm перечитать конфигурацию."""
    values = stored()
    values[LEGACY_KEYS.get(key, key)] = value
    write(values)
    nudge()
    return value


def toggle(key):
    return set(key, not get(key))


def nudge():
    """Переписать .wezterm.lua теми же байтами — только ради времени правки."""
    try:
        with io.open(WEZTERM, 'rb') as handle:
            data = handle.read()
        with io.open(WEZTERM, 'wb') as handle:
            handle.write(data)
    except OSError:
        pass
