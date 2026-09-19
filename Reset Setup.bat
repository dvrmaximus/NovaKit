@echo off
cd /d "%~dp0"
if exist "data\setup_done.flag" del /f /q "data\setup_done.flag"
if exist ".env" del /f /q ".env"
echo Profil efface. Relance NovaKit pour refaire le setup.
pause
