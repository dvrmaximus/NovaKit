"""Démarre / ouvre le panel admin local (créateur seulement)."""

from __future__ import annotations

import socket
import threading
import time
import urllib.request
import webbrowser

from config import DATA_DIR
from online.db import (
    importer_journal_local,
    lire_identifiants_fichier,
    set_admin_password,
)
from online.server import PORT, app

_started = False
_lock = threading.Lock()

# Identifiants créateur (toi uniquement)
ADMIN_USER = "Lutre"
ADMIN_PASS = "LutreAdmin"


def est_createur() -> bool:
    """True uniquement si le panel admin a été initialisé en local.

    Le fichier data/admin_credentials.txt (gitignoré) est créé par les
    outils dans creator/ — jamais par le simple téléchargement GitHub.
    Ne pas se baser sur creator.json (partagé avec les potes).
    """
    try:
        return (DATA_DIR / "admin_credentials.txt").exists()
    except Exception:
        return False


def _port_libre(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def serveur_ok() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
            return getattr(r, "status", 200) == 200
    except Exception:
        return False


def demarrer_admin_local(ouvrir: bool = True, reset_mdp: bool = True) -> str:
    """
    Lance le panel admin sur http://127.0.0.1:8788
    Compte créateur : Lutre / LutreAdmin
    Force la reconnexion à chaque ouverture.
    """
    global _started
    DATA_DIR.mkdir(exist_ok=True)

    if reset_mdp:
        set_admin_password(ADMIN_USER, ADMIN_PASS)

    # Toujours invalider les sessions → il faut se reconnecter pour voir
    try:
        from online.db import _conn, init_db
        init_db()
        with _conn() as c:
            c.execute("DELETE FROM sessions")
    except Exception:
        pass

    try:
        importer_journal_local()
    except Exception:
        pass

    with _lock:
        if not serveur_ok():
            if not _port_libre(PORT) and not serveur_ok():
                # Port occupé mais pas de health → on tente quand même d'ouvrir
                pass
            else:
                def _run():
                    import uvicorn
                    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning", access_log=False)

                threading.Thread(target=_run, daemon=True, name="novakit-admin").start()
                _started = True
                for _ in range(50):
                    if serveur_ok():
                        break
                    time.sleep(0.2)

    url = f"http://127.0.0.1:{PORT}"
    if ouvrir:
        webbrowser.open(url)
    return url


def infos_connexion() -> dict:
    set_admin_password(ADMIN_USER, ADMIN_PASS)
    return {
        "url": f"http://127.0.0.1:{PORT}",
        "username": ADMIN_USER,
        "password": ADMIN_PASS,
    }
