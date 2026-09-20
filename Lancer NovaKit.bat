@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONPATH=%~dp0"
title NovaKit

REM Lance main.py via pythonw/pyw (pas de console, pas de VBS).
REM On utilise "start" pour ne pas bloquer — comportement normal d'un lanceur app.

set "PYW="
if exist "%LocalAppData%\Programs\Python\Python312\pythonw.exe" (
  set "PYW=%LocalAppData%\Programs\Python\Python312\pythonw.exe"
) else if exist "%LocalAppData%\Programs\Python\Python313\pythonw.exe" (
  set "PYW=%LocalAppData%\Programs\Python\Python313\pythonw.exe"
) else if exist "%LocalAppData%\Programs\Python\Python311\pythonw.exe" (
  set "PYW=%LocalAppData%\Programs\Python\Python311\pythonw.exe"
)

if defined PYW (
  start "NovaKit" "%PYW%" "%~dp0main.py"
  exit /b 0
)

where pyw >nul 2>&1
if %errorlevel%==0 (
  start "NovaKit" pyw -3 "%~dp0main.py"
  exit /b 0
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
  start "NovaKit" pythonw "%~dp0main.py"
  exit /b 0
)

echo.
echo  Python introuvable.
echo  1. Installe Python 3 depuis https://www.python.org/downloads/
echo     (coche "Add python.exe to PATH")
echo  2. Relance install.bat
echo  3. Puis ce fichier : Lancer NovaKit.bat
echo.
pause
exit /b 1
