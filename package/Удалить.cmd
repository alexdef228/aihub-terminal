@echo off
chcp 65001 >nul
title Удаление AIHUB Терминала
set "HERE=%~dp0"
:: Уходим из папки программы, иначе её нельзя будет удалить
cd /d "%TEMP%"
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY py -3 -c "import sys" >nul 2>nul && set "PY=py -3"
if not defined PY (
  echo   Python не найден — удали папку "%HERE%" и ярлыки вручную.
  pause
  exit /b 1
)
%PY% "%HERE%setup.py" --uninstall
echo.
pause
