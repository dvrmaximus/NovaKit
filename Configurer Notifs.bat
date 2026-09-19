@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONPATH=%~dp0
pyw -3 -c "import sys; sys.path.insert(0, r'%~dp0'); from ui.creator_config import lancer_config_createur; lancer_config_createur()"
if errorlevel 1 py -3 -c "import sys; sys.path.insert(0, r'%~dp0'); from ui.creator_config import lancer_config_createur; lancer_config_createur()"
