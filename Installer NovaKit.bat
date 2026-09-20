@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NovaKit — Installation
color 0B

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║                                                          ║
echo  ║              N O V A K I T   —   INSTALL                 ║
echo  ║         HUD type Jarvis · installation simple            ║
echo  ║                                                          ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.
echo  Ce script fait tout le nécessaire pour lancer NovaKit.
echo  Tu as besoin de Python 3 (option « Add to PATH » cochée).
echo.
echo  ────────────────────────────────────────────────────────────
echo   ÉTAPE 1 / 3  —  Vérifier Python
echo  ────────────────────────────────────────────────────────────
echo.

set "PYOK="
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 --version 2>nul
  if not errorlevel 1 set "PYOK=1"
)
if not defined PYOK (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python --version 2>nul
    if not errorlevel 1 set "PYOK=1"
  )
)

if not defined PYOK (
  echo  [!] Python introuvable.
  echo.
  echo  1. Ouvre https://www.python.org/downloads/
  echo  2. Installe Python 3 et coche « Add python.exe to PATH »
  echo  3. Relance ce fichier : Installer NovaKit.bat
  echo.
  start "" "https://www.python.org/downloads/"
  pause
  exit /b 1
)

echo  [OK] Python détecté.
echo.
echo  ────────────────────────────────────────────────────────────
echo   ÉTAPE 2 / 3  —  Installer les dépendances
echo  ────────────────────────────────────────────────────────────
echo.

set "PIPCMD="
where py >nul 2>&1
if %errorlevel%==0 (
  set "PIPCMD=py -3 -m pip"
) else (
  set "PIPCMD=python -m pip"
)

%PIPCMD% install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  [!] Échec de pip. Vérifie ta connexion internet, puis réessaie.
  pause
  exit /b 1
)

echo.
echo  [OK] Dépendances installées.
echo.
echo  ────────────────────────────────────────────────────────────
echo   ÉTAPE 3 / 3  —  C’est prêt
echo  ────────────────────────────────────────────────────────────
echo.
echo  Prochaine action : double-clique « Lancer NovaKit.bat »
echo  Au premier lancement, un assistant te demande :
echo    · ton pseudo
echo    · le nom de ton IA
echo    · une clé Google Gemini  (gratuite)
echo.
echo  Clé Gemini : https://aistudio.google.com/apikey
echo.

REM Page de bienvenue locale (optionnelle)
if exist "%~dp0docs\installe.html" (
  start "" "%~dp0docs\installe.html"
)

echo  Lancer NovaKit maintenant ?  [O]ui  /  [N]on
choice /C ON /N /M "  "
if errorlevel 2 goto fin
if errorlevel 1 (
  call "%~dp0Lancer NovaKit.bat"
  exit /b 0
)

:fin
echo.
echo  Quand tu veux : double-clique « Lancer NovaKit.bat »
echo.
pause
exit /b 0
