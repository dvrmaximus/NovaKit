@echo off
title NovaKit — Installation
cd /d "%~dp0"
echo.
echo  === NovaKit — installation des dependances ===
echo.
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo Echec pip. Verifie que Python est installe : https://www.python.org/downloads/
  pause
  exit /b 1
)
echo.
echo  OK. Double-clique maintenant sur "Lancer NovaKit.vbs"
echo  Au premier lancement : wizard (nom IA, cle Gemini, PIN).
echo.
pause
