@echo off
chcp 65001 >nul
title Установка AIHUB Терминала
cd /d "%~dp0"

:: Установщику нужен Python (на нём же работает список проектов в окне).
:: Нет — ставим через winget, он есть в Windows 10/11.
set "PY="
call :findpy
if not defined PY (
  echo.
  echo   Python не найден. Ставлю Python 3.12 через winget — пара минут…
  winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
  call :findpy
)
if not defined PY (
  echo.
  echo   Python так и не нашёлся. Поставь его с python.org ^(галочка «Add to PATH»^)
  echo   и запусти «Установить.cmd» ещё раз.
  pause
  exit /b 1
)

"%PY%" "%~dp0setup.py" %*
echo.
pause
exit /b

:findpy
python -c "import sys" >nul 2>nul && (for /f "delims=" %%E in ('python -c "import sys;print(sys.executable)"') do set "PY=%%E") && exit /b
py -3 -c "import sys" >nul 2>nul && (for /f "delims=" %%E in ('py -3 -c "import sys;print(sys.executable)"') do set "PY=%%E") && exit /b
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY=%%D\python.exe"
exit /b
