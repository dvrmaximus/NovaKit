@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NovaKit — Build application
echo.
echo  Construction de NovaKit.exe (quelques minutes)...
echo.
py -3 -m pip install -q pyinstaller pillow
if errorlevel 1 (
  echo Echec installation PyInstaller.
  pause
  exit /b 1
)
py -3 -m PyInstaller --noconfirm novakit.spec
if errorlevel 1 (
  echo Build echoue.
  pause
  exit /b 1
)
echo.
echo  OK → dist\NovaKit\NovaKit.exe
echo  Lance ensuite "Installer Application.bat"
echo.
pause
