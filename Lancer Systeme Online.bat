@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NovaKit — Systeme Online
set PYTHONPATH=%~dp0
echo Lancement du panel admin + tunnel public...
echo Laisse cette fenetre ouverte.
echo.
py -3 online\launcher.py
if errorlevel 1 python online\launcher.py
pause
