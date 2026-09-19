import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from config import BASE_DIR, ENABLE_TUNNEL, NGROK_AUTHTOKEN, NGROK_DOMAIN, REMOTE_PORT, TUNNEL_MODE
from remote import state

URL_FILE = BASE_DIR / "data" / "url_mobile.txt"
DESKTOP_URL = Path.home() / "Desktop" / "URL Astat Mobile.txt"
ERROR_LOG = BASE_DIR / "data" / "tunnel_error.log"
CLOUDFLARED = BASE_DIR / "bin" / "cloudflared.exe"

_process = None
_watchdog_ok = False


def _log(msg: str):
    ERROR_LOG.parent.mkdir(exist_ok=True)
    with open(ERROR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


def _sauver_url(url: str, provider: str):
    state.public_url = url
    state.tunnel_actif = True
    state.tunnel_erreur = ""
    state.tunnel_provider = provider
    texte = (
        f"URL Astat — controle PC depuis ton telephone\n"
        f"{'=' * 40}\n\n"
        f"{url}\n\n"
        f"PIN : voir .env (REMOTE_PIN)\n"
        f"Fournisseur : {provider}\n\n"
        f"IMPORTANT :\n"
        f"- Astat doit rester OUVERT sur le PC\n"
        f"- Si l'URL change, utilise TOUJOURS ce fichier (il se met a jour)\n"
        f"- Pour une URL FIXE : ajoute NGROK_DOMAIN dans .env\n"
        f"  (domaine gratuit sur https://dashboard.ngrok.com/domains )\n"
    )
    URL_FILE.write_text(texte, encoding="utf-8")
    try:
        DESKTOP_URL.write_text(texte, encoding="utf-8")
    except Exception:
        pass


def _tuer_tunnels():
    global _process
    if _process and _process.poll() is None:
        try:
            _process.terminate()
        except Exception:
            pass
    _process = None
    from win_silent import run_silent
    try:
        run_silent(["taskkill", "/F", "/IM", "cloudflared.exe"], check=False)
        run_silent(["taskkill", "/F", "/IM", "ngrok.exe"], check=False)
    except Exception:
        pass
    try:
        from pyngrok import ngrok
        ngrok.kill()
    except Exception:
        pass


def demarrer_tunnel(skip_delay=False):
    global _watchdog_ok
    if not ENABLE_TUNNEL:
        state.tunnel_erreur = "Tunnel desactive"
        return None

    if not skip_delay:
        time.sleep(3)
    ERROR_LOG.write_text("", encoding="utf-8")
    _tuer_tunnels()

    url = None
    if TUNNEL_MODE == "ngrok" and NGROK_AUTHTOKEN:
        url = _tunnel_ngrok()
    if not url:
        url = _tunnel_cloudflared()
    if not url and TUNNEL_MODE != "ngrok" and NGROK_AUTHTOKEN:
        url = _tunnel_ngrok()

    if not url and not state.tunnel_erreur:
        state.tunnel_erreur = "Tunnel impossible — voir data/tunnel_error.log"

    if not _watchdog_ok:
        _watchdog_ok = True
        threading.Thread(target=_surveiller_tunnel, daemon=True).start()

    return url


def _tunnel_ngrok():
    try:
        from win_silent import patch_subprocess_no_window
        patch_subprocess_no_window()
        from pyngrok import conf, ngrok
        ngrok.set_auth_token(NGROK_AUTHTOKEN)
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        port = state.port_actif or REMOTE_PORT
        options = {}
        if NGROK_DOMAIN:
            options["domain"] = NGROK_DOMAIN
        tunnel = ngrok.connect(port, "http", **options)
        url = tunnel.public_url or ""
        if url.startswith("http://"):
            url = "https://" + url[7:]
        label = "ngrok-fixe" if NGROK_DOMAIN else "ngrok"
        _sauver_url(url, label)
        _log(f"Ngrok OK ({label}) : {url}")
        return url
    except Exception as exc:
        msg = str(exc)
        _log(f"Ngrok erreur : {msg}")
        state.tunnel_erreur = f"Ngrok : {msg[:50]}"
    return None


def _telecharger_cloudflared() -> str:
    CLOUDFLARED.parent.mkdir(exist_ok=True)
    if CLOUDFLARED.exists():
        return str(CLOUDFLARED)
    _log("Telechargement cloudflared...")
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    urllib.request.urlretrieve(url, CLOUDFLARED)
    return str(CLOUDFLARED)


def _tunnel_cloudflared():
    global _process
    try:
        exe = _telecharger_cloudflared()
        port = state.port_actif or REMOTE_PORT
        from win_silent import popen_silent
        _process = popen_silent(
            [exe, "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        result = {"url": None}

        def _lire():
            for _ in range(120):
                if _process.poll() is not None:
                    break
                line = _process.stdout.readline()
                if not line:
                    continue
                _log(f"cloudflared: {line.strip()}")
                match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if match:
                    result["url"] = match.group(0)
                    return

        t = threading.Thread(target=_lire, daemon=True)
        t.start()
        t.join(timeout=45)

        if result["url"]:
            from remote.startup import attendre_serveur
            if attendre_serveur(timeout=5):
                _sauver_url(result["url"], "cloudflare")
                _log(f"Cloudflare OK : {result['url']}")
                return result["url"]
            state.tunnel_erreur = "502 — serveur pas pret"
            _log("Cloudflare URL ok mais serveur local KO")

        state.tunnel_erreur = "Cloudflare timeout"
    except Exception as exc:
        state.tunnel_erreur = f"Cloudflare : {str(exc)[:50]}"
        _log(f"Cloudflare erreur : {exc}")
    return None


def _surveiller_tunnel():
    """Relance le tunnel si le process cloudflared meurt."""
    from remote.startup import serveur_local_ok

    while True:
        time.sleep(25)
        if not ENABLE_TUNNEL:
            continue
        if not serveur_local_ok():
            state.tunnel_erreur = "Serveur local arrete"
            continue
        if _process is not None and _process.poll() is not None:
            _log("cloudflared arrete — reconnexion")
            state.tunnel_actif = False
            state.tunnel_erreur = "Reconnexion..."
            demarrer_tunnel(skip_delay=True)
