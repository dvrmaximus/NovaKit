import threading
import time
import urllib.error
import urllib.request

from config import REMOTE_PORT
from remote import state


def port_actif() -> int:
    return state.port_actif or REMOTE_PORT


def attendre_serveur(timeout: int = 60) -> bool:
    """Attend que le serveur local reponde sur /health."""
    fin = time.time() + timeout
    while time.time() < fin:
        if state.serveur_erreur:
            state.server_ready = False
            return False
        try:
            url = f"http://127.0.0.1:{port_actif()}/health"
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    state.server_ready = True
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(0.8)
    state.server_ready = False
    return False


def _attendre_tunnel(url: str, timeout: int = 40) -> bool:
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=6) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(2)
    return False


def serveur_local_ok() -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port_actif()}/health", timeout=3
        ) as resp:
            return resp.status == 200
    except Exception:
        return False


def demarrer_remote_complet(on_pret=None, on_erreur=None):
    """Demarre serveur puis tunnel dans le bon ordre."""
    from remote.server import demarrer_serveur
    from remote.tunnel import demarrer_tunnel

    threading.Thread(target=demarrer_serveur, daemon=True).start()

    if not attendre_serveur():
        if state.serveur_erreur:
            derniere = state.serveur_erreur.strip().splitlines()[-1]
            state.tunnel_erreur = f"Serveur KO : {derniere[:70]}"
        else:
            state.tunnel_erreur = f"Serveur local KO (port {port_actif()})"
        if on_erreur:
            on_erreur(state.tunnel_erreur)
        return None

    time.sleep(1)
    url = demarrer_tunnel(skip_delay=True)

    # Le tunnel public peut mettre quelques secondes (ngrok splash / cloudflare)
    if url:
        ok = _attendre_tunnel(url, timeout=50)
        if on_pret:
            on_pret(url)
        if not ok and on_erreur:
            # URL donnée quand même — souvent utilisable après 1-2 refresh
            pass
        return url

    if on_erreur:
        on_erreur(state.tunnel_erreur or "Tunnel echoue")
    return None
