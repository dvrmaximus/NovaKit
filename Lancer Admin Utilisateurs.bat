@echo off
chcp 65001 >nul
cd /d "%~dp0"
title NovaKit — Admin (createur)
set PYTHONPATH=%~dp0
echo.
echo  Admin createur UNIQUEMENT
echo  Utilisateur : Lutre
echo  Mot de passe : LutreAdmin
echo  URL : http://127.0.0.1:8788
echo.
py -3 -c "import sys,time; sys.path.insert(0, r'%~dp0'); from online.db import reset_utilisateurs, reset_admin_createur; from online.admin_local import demarrer_admin_local; print('users reset', reset_utilisateurs()); reset_admin_createur('Lutre','LutreAdmin'); print(demarrer_admin_local(True, True)); time.sleep(86400)"
pause
