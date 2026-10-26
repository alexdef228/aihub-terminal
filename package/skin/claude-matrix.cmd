@echo off
chcp 65001 >nul
setlocal

:: «Планы» (TaskNotes) находят AIHUB по реестру. Отмечаемся при каждом
:: запуске — и с ярлыка проекта, не только из меню (там же plans_link.py).
:: Переложили папку — ключ поправится при следующем запуске.
set "AIHUB_DIR=%~dp0"
reg add "HKCU\Software\AIHUB\TerminalSkin" /v Dir /d "%AIHUB_DIR:~0,-1%" /f >nul 2>&1

:: Запуск Claude Code в матричном окне. Вызывается из WezTerm (Ctrl+Shift+P,
:: см. wezterm.lua), но работает и сам по себе — из ярлыка или любого шелла.
::
::   claude-matrix.cmd ["путь\к\проекту"] ["первое сообщение Claude"]
::
:: Без аргумента Claude Code стартует в текущей папке. Где лежит claude.exe
:: и нужен ли прокси, решает launch_agent.py (см. настройки.json).

set "PROJECT=%~1"
if not defined PROJECT set "PROJECT=%CD%"
:: Второй аргумент — первое сообщение (так «Планы» дают задачу «в работу»)
python "%~dp0launch_agent.py" claude "%PROJECT%" %2
