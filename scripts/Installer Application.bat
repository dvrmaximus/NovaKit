@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title NovaKit — Installer l'application
set "SRC=%CD%\dist\NovaKit"
set "DEST=%LOCALAPPDATA%\Programs\NovaKit"

if not exist "%SRC%\NovaKit.exe" (
  echo Build manquant. Lance d'abord "scripts\Build Application.bat"
  pause
  exit /b 1
)

echo.
echo  Installation dans :
echo  %DEST%
echo.

if not exist "%DEST%" mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /E /XO /NFL /NDL /NJH /NJS /nc /ns /np >nul
if errorlevel 8 (
  echo Copie echouee.
  pause
  exit /b 1
)

REM Raccourcis Bureau + Menu Demarrer
powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\create_shortcuts.ps1" -ExePath "%DEST%\NovaKit.exe" -IconPath "%DEST%\assets\novakit.ico"
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\create_shortcuts.ps1" -ExePath "%DEST%\NovaKit.exe"
)

echo.
echo  NovaKit est installe comme application.
echo  Raccourci sur le Bureau + Menu Demarrer.
echo.
start "" "%DEST%\NovaKit.exe"
pause
