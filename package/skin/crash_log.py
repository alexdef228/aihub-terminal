# -*- coding: utf-8 -*-
"""Падение консоли должно оставлять след.

Зачем. Консоль рисуется на альтернативном экране: prompt_toolkit при выходе
возвращает основной, а меню сразу за этим чистит его целиком (`\\033[2J`).
Traceback живёт на экране доли секунды, и разговор сводится к «консоль резко
упала» — чинить нечего. Теперь любая ошибка пишется в
`session-memory/crash.log` со временем и PID: файл переживает и падение, и
закрытие вкладки, и его можно прочитать хоть через час.

Второе назначение — не давать одной ошибке ронять весь интерфейс. Сбой
обработчика клавиши, отрисовки или разбора события Codex раньше вылетал из
`Application.run_async()` и уносил процесс, оставляя живой `codex.exe`.
Здесь эти три места оборачиваются: ошибка попадает в лог и на экран, консоль
продолжает работать.
"""
import os
from pathlib import Path
import time
import traceback

LOG = Path(__file__).resolve().parent / 'session-memory' / 'crash.log'

# Отрисовка зовётся по пять раз в секунду: без этого одна и та же ошибка
# за минуту раздула бы лог на сотни повторов.
_seen = {}


def _trace(error=None):
    if error is None:
        return traceback.format_exc()
    return ''.join(traceback.format_exception(type(error), error, error.__traceback__))


def write(where, error=None):
    """Записать ошибку. Возвращает короткую строку для показа на экране."""
    trace = _trace(error).strip()
    lines = trace.splitlines()
    summary = lines[-1] if lines else 'неизвестная ошибка'
    key = (where, summary)
    if key in _seen:
        _seen[key] += 1
        return summary + '  ░  повтор №{} · {}'.format(_seen[key], LOG)
    _seen[key] = 1
    note('{}\n{}'.format(where, trace))
    return summary + '  ░  подробности: ' + str(LOG)


def note(text):
    """Строка в тот же лог без исключения — отметить событие вроде выхода по сторожу."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('a', encoding='utf-8') as handle:
            handle.write('\n=== {} · pid {} ===\n{}\n'.format(
                time.strftime('%d.%m.%Y %H:%M:%S'), os.getpid(), text))
    except OSError:
        pass


def render(function):
    """Обёртка для функции отрисовки: сбой рисует красную строку, а не роняет консоль."""
    def draw():
        try:
            return function()
        except Exception as error:
            return [('class:red', '  сбой отрисовки: ' + write(
                'отрисовка ' + getattr(function, '__name__', '?'), error))]
    draw.__name__ = getattr(function, '__name__', 'draw')
    return draw


def protect(bindings, report):
    """Обернуть все обработчики клавиш: ошибка показывается, а не убивает приложение.

    `report(где, ошибка)` — метод консоли: пишет в лог и добавляет сообщение
    в ленту. Обработчики подменяются на месте, уже собранные Binding — те же
    объекты, поэтому кэш prompt_toolkit трогать не нужно.
    """
    for binding in bindings.bindings:
        binding.handler = guard(binding.handler, report,
                                'клавиша ' + getattr(binding.handler, '__name__', '?'))


def guard(function, report, where):
    """Тот же приём для одиночной функции — обработчика мыши, разбора события."""
    def wrapper(*args, **values):
        try:
            return function(*args, **values)
        except Exception as error:
            report(where, error)
    wrapper.__name__ = getattr(function, '__name__', 'wrapper')
    return wrapper
