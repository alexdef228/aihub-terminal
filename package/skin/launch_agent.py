"""Launch either assistant in the menu's terminal, with native resume or a handoff."""
import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import console_guard
import crash_log
import session_store as history
import skin_settings
from rpc_client import executable as codex_executable
from texts import t

HERE = Path(__file__).resolve().parent


def detector_path():
    script = skin_settings.proxy_script()
    return Path(script) if script else None


def announce_check():
    """Строка «Проверяю соединение…» — первой, до всего остального.

    Меню уже стёрло экран, а скрипт прокси может думать несколько секунд.
    Пока на экране ничего не происходит, это выглядит как зависший чёрный
    терминал, поэтому строка печатается раньше поиска сессии и сборки
    команды, а не перед самим запуском PowerShell.
    """
    detector = detector_path()
    if detector and detector.is_file():
        print(t("checking_connection"), flush=True)


def proxy_environment():
    """Необязательный скрипт прокси из настроек: печатает адрес последней строкой.

    Нужен тем, у кого прокси меняется от сети к сети. Скрипта нет —
    помощник получает окружение как есть (HTTP_PROXY и прочее из системы).
    """
    env = os.environ.copy()
    detector = detector_path()
    if detector and detector.is_file():
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(detector)], capture_output=True, timeout=35)
            proxy = result.stdout.decode('utf-8', errors='replace').strip().splitlines()
            if result.returncode == 0 and proxy and proxy[-1].startswith(('http://', 'https://', 'socks5://')):
                for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'):
                    env[key] = proxy[-1]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return env


def build_command(provider, project, source=None, prompt=None):
    """Let the native clients own input, slash menus, settings and rendering."""
    if provider == 'codex':
        command = [codex_executable()]
        if source and source['provider'] == 'codex':
            command += ['resume', source['id']]
        command += ['--no-alt-screen', '--cd', project]
        if source and source['provider'] != 'codex':
            entry = history.save(source)
            if not entry:
                raise ValueError(t("handoff_unreadable"))
            command += [t("handoff_codex").format(entry['markdown'])]
        elif prompt:
            command += [prompt]
        return command
    if provider != 'claude':
        raise ValueError(t("unknown_assistant") + provider)
    command = [claude_executable()]
    if source and source['provider'] == 'claude':
        command += ['--resume', source['id']]
    elif source:
        entry = history.save(source)
        if not entry:
            raise ValueError(t("handoff_unreadable"))
        command += [t("handoff_claude").format(entry['markdown'])]
    elif prompt:
        # Первое сообщение от вызвавшего (claude-matrix.cmd "папка" "задача")
        command += [prompt]
    return command


def claude_executable():
    """Настоящий claude.exe: npm-установка, штатный установщик или PATH.

    exe предпочтительнее обёртки claude.cmd: через cmd.exe аргументы
    с кавычками и переводами строк (передача переписки) доезжают битыми.
    """
    appdata = os.environ.get('APPDATA', str(history.USER / 'AppData/Roaming'))
    for candidate in (
            Path(appdata) / 'npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe',
            history.USER / '.local/bin/claude.exe'):
        if candidate.is_file():
            return str(candidate)
    found = shutil.which('claude.exe') or shutil.which('claude')
    if not found:
        raise FileNotFoundError(t("claude_missing"))
    return found


@contextmanager
def native_console_input():
    """The menu's VT-input mode must not leak into a child console client."""
    saved = None
    if os.name == 'nt':
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        kernel.GetStdHandle.restype = wintypes.HANDLE
        kernel.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetConsoleMode.restype = wintypes.BOOL
        kernel.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.SetConsoleMode.restype = wintypes.BOOL
        kernel.FlushConsoleInputBuffer.argtypes = [wintypes.HANDLE]
        kernel.FlushConsoleInputBuffer.restype = wintypes.BOOL
        handle = kernel.GetStdHandle(-10 & 0xffffffff)
        mode = wintypes.DWORD()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            # Cooked input for startup; the native TUI selects its own raw mode.
            if kernel.SetConsoleMode(handle, (mode.value & ~0x0240) | 0x0087):
                saved = (kernel, handle, mode.value)
        # The menu acts on mouse press; the release (ESC[<0;x;ym) and the Enter
        # key-up stay queued. The assistant read that ESC as "interrupt" and
        # aborted the handoff prompt seconds after sending it. Drop the
        # leftovers once the proxy check is done and everything has arrived.
        kernel.FlushConsoleInputBuffer(handle)
    try:
        yield
    finally:
        if saved:
            kernel, handle, mode = saved
            kernel.SetConsoleMode(handle, mode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('provider', choices=['claude', 'codex'])
    parser.add_argument('project')
    parser.add_argument('prompt', nargs='?')
    parser.add_argument('--session')
    args = parser.parse_args()
    announce_check()
    project = str(Path(args.project).resolve())
    if not Path(project).is_dir():
        raise ValueError(t("project_missing") + project)
    source = None
    if args.session:
        source = next((s for s in history.sessions(project) if s['provider'] + ':' + s['id'] == args.session), None)
        if not source:
            raise ValueError(t("session_gone"))
    command = build_command(args.provider, project, source, args.prompt)
    started = time.time()
    # Запускаем через Popen, чтобы сторож вкладки знал, кого уводить с
    # собой: закрытая вкладка не должна оставлять живой Claude Code.
    env = proxy_environment()
    with native_console_input():
        child = subprocess.Popen(command, cwd=project, env=env)
        console_guard.watch(lambda: console_guard.kill_tree(child.pid))
        code = child.wait()
    for session in history.sessions(project):
        if session['provider'] == args.provider and session['when'] >= started:
            history.save(session)
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(t("launch_error") + str(error))
        sys.exit(1)
    except Exception as error:
        # Падение запуска раньше уносило traceback вместе с окном.
        print(t("launch_crashed") + crash_log.write('запуск помощника', error))
        sys.exit(1)
