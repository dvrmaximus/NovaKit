"""Ouvrir n'importe quelle application Windows — sans terminal."""

from __future__ import annotations

import os
import re
from pathlib import Path

from win_silent import run_silent, shell_open

# Alias courants → cible ShellExecute / exe
APPLICATIONS_CONNUES = {
    "calculatrice": "calc.exe",
    "calculette": "calc.exe",
    "calc": "calc.exe",
    "bloc-notes": "notepad.exe",
    "bloc notes": "notepad.exe",
    "notepad": "notepad.exe",
    "explorateur": "explorer.exe",
    "explorer": "explorer.exe",
    "fichiers": "explorer.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "spotify": "spotify.exe",
    "discord": "discord.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "code": "code.exe",
    "cursor": "cursor.exe",
    "steam": "steam.exe",
    "epic": "EpicGamesLauncher.exe",
    "epic games": "EpicGamesLauncher.exe",
    "whatsapp": "whatsapp.exe",
    "telegram": "telegram.exe",
    "vlc": "vlc.exe",
    "obs": "obs64.exe",
    "photoshop": "photoshop.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "parametres": "ms-settings:",
    "paramètres": "ms-settings:",
    "settings": "ms-settings:",
    "gestionnaire des taches": "taskmgr.exe",
    "task manager": "taskmgr.exe",
}


def _norm(texte: str) -> str:
    t = (texte or "").lower().strip()
    for a, b in (
        ("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ù", "u"),
        ("ô", "o"), ("î", "i"), ("ç", "c"),
    ):
        t = t.replace(a, b)
    t = re.sub(r"\.(exe|lnk|bat|cmd)$", "", t)
    return re.sub(r"\s+", " ", t).strip(" \"'")


def _start_menu_roots() -> list[Path]:
    roots = []
    appdata = os.environ.get("APPDATA")
    progdata = os.environ.get("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if progdata:
        roots.append(Path(progdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return [r for r in roots if r.exists()]


def _chercher_raccourci(nom: str) -> Path | None:
    """Cherche un .lnk dans le menu Démarrer (correspondance partielle)."""
    q = _norm(nom)
    if not q or len(q) < 2:
        return None
    candidats: list[tuple[int, Path]] = []
    for root in _start_menu_roots():
        try:
            for lnk in root.rglob("*.lnk"):
                stem = _norm(lnk.stem)
                if q == stem:
                    return lnk
                if q in stem or stem in q:
                    # score : plus court = plus précis
                    candidats.append((abs(len(stem) - len(q)), lnk))
        except (PermissionError, OSError):
            continue
    if not candidats:
        return None
    candidats.sort(key=lambda x: x[0])
    return candidats[0][1]


def _chercher_exe(nom: str) -> Path | None:
    """Cherche un .exe dans Program Files / LocalAppData (profondeur limitée)."""
    q = _norm(nom)
    if not q:
        return None
    noms = {q, q.replace(" ", ""), f"{q}.exe"}
    bases = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
    ]
    patterns = ("*.exe", "*/*.exe", "*/*/*.exe", "*/*/*/*.exe")
    for base in bases:
        if not base or not base.exists():
            continue
        for pat in patterns:
            try:
                for exe in base.glob(pat):
                    if _norm(exe.stem) in noms or _norm(exe.name) in noms:
                        n = exe.name.lower()
                        if any(x in n for x in ("unins", "update", "setup", "installer")):
                            continue
                        return exe
            except (PermissionError, OSError):
                continue
    return None


def _via_where(nom: str) -> str | None:
    try:
        r = run_silent(["where", nom], text=True, timeout=5, check=False)
        if r.returncode == 0 and r.stdout:
            line = r.stdout.strip().splitlines()[0].strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return None


def _via_startapps(nom: str) -> bool:
    """Dernier recours : Get-StartApps (PowerShell caché)."""
    q = nom.replace("'", "''")
    script = (
        f"$a = Get-StartApps | Where-Object {{ $_.Name -like '*{q}*' }} "
        f"| Select-Object -First 1; "
        f"if ($a) {{ Start-Process \"shell:AppsFolder\\$($a.AppID)\"; exit 0 }} "
        f"else {{ exit 1 }}"
    )
    try:
        r = run_silent(
            [
                "powershell", "-NoProfile", "-NonInteractive",
                "-WindowStyle", "Hidden", "-Command", script,
            ],
            timeout=20, check=False,
        )
        return r.returncode == 0
    except Exception:
        return False


def ouvrir_application(nom_application: str) -> str:
    """Ouvre n'importe quelle application installée sur le PC (Chrome, Discord, Calculatrice, jeu, etc.).

    Args:
        nom_application: nom de l'app (ex: Chrome, Spotify, Blender, Calculatrice)
    """
    brut = (nom_application or "").strip()
    if not brut:
        return "Dis-moi quelle application ouvrir."

    nom = _norm(brut)
    cible = APPLICATIONS_CONNUES.get(nom, brut)

    # 1) Alias / nom direct via ShellExecute (aucune console)
    if shell_open(str(cible)):
        return f"{brut} ouvert."

    # 2) Raccourci menu Démarrer
    lnk = _chercher_raccourci(brut)
    if lnk and shell_open(str(lnk)):
        return f"{lnk.stem} ouvert."

    # 3) where.exe (PATH)
    found = _via_where(cible if cible.endswith(".exe") else f"{nom}.exe")
    if not found:
        found = _via_where(nom)
    if found and shell_open(found):
        return f"{brut} ouvert."

    # 4) Cherche .exe dans Program Files (un peu plus lent)
    exe = _chercher_exe(brut)
    if exe and shell_open(str(exe)):
        return f"{exe.stem} ouvert."

    # 5) Apps du menu Démarrer (UWP / Store)
    if _via_startapps(brut):
        return f"{brut} ouvert."

    return (
        f"Je ne trouve pas « {brut} ». "
        "Vérifie le nom (comme dans le menu Démarrer) et réessaie."
    )


def _volume_interface():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def obtenir_volume() -> str:
    """Renvoie le volume actuel du système (0 à 100)."""
    try:
        volume = _volume_interface()
        niveau = int(volume.GetMasterVolumeLevelScalar() * 100)
        return f"Le volume est à {niveau} %."
    except Exception as erreur:
        return f"Impossible de lire le volume : {erreur}"


def ajuster_volume(variation: int) -> str:
    """Augmente ou diminue le volume relativement (-100 à +100).

    Args:
        variation: positif pour monter, négatif pour baisser (ex: 20 ou -20)
    """
    try:
        volume = _volume_interface()
        actuel = int(volume.GetMasterVolumeLevelScalar() * 100)
        nouveau = max(0, min(100, actuel + int(variation)))
        volume.SetMasterVolumeLevelScalar(nouveau / 100, None)
        return f"Volume ajusté à {nouveau} %."
    except Exception as erreur:
        return f"Impossible d'ajuster le volume : {erreur}"


def regler_volume(niveau: int) -> str:
    """Règle le volume système entre 0 et 100.

    Args:
        niveau: volume cible de 0 (muet) à 100 (max)
    """
    try:
        niveau = max(0, min(100, int(niveau)))
        volume = _volume_interface()
        volume.SetMasterVolumeLevelScalar(niveau / 100, None)
        return f"Volume réglé à {niveau} %."
    except Exception as erreur:
        return f"Impossible de régler le volume : {erreur}"
