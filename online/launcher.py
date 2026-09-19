"""Lance le système online : API admin + tunnel public Cloudflare."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import BASE_DIR, DATA_DIR
from core.notify_creator import charger_creator, sauver_creator
from online.db import CREDS_FILE, ensure_admin
from online.server import PORT

CLOUDFLARED = BASE_DIR / "bin" / "cloudflared.exe"
URL_FILE = DATA_DIR / "url_admin_online.txt"
_tunnel_proc = None


def _msg(titre: str, texte: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, texte, titre, 0x40)
    except Exception:
        print(titre, texte)


def _telecharger_cloudflared() -> str:
    CLOUDFLARED.parent.mkdir(exist_ok=True)
    if CLOUDFLARED.exists():
        return str(CLOUDFLARED)
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    urllib.request.urlretrieve(url, CLOUDFLARED)
    return str(CLOUDFLARED)


def _attendre_local(timeout: float = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def _tunnel() -> str | None:
    global _tunnel_proc
    try:
        from win_silent import popen_silent
    except Exception:
        popen_silent = subprocess.Popen  # type: ignore

    exe = _telecharger_cloudflared()
    _tunnel_proc = popen_silent(
        [exe, "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    found = {"url": None}

    def _lire():
        for _ in range(150):
            if _tunnel_proc.poll() is not None:
                break
            line = _tunnel_proc.stdout.readline()
            if not line:
                continue
            print(line.strip())
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m:
                found["url"] = m.group(0)
                return

    t = threading.Thread(target=_lire, daemon=True)
    t.start()
    t.join(timeout=50)
    return found["url"]


def main():
    DATA_DIR.mkdir(exist_ok=True)
    user, pwd, created = ensure_admin("Lutre")

    # Serveur uvicorn dans un thread
    def _run():
        import uvicorn
        uvicorn.run("online.server:app", host="127.0.0.1", port=PORT, log_level="info")

    threading.Thread(target=_run, daemon=True).start()
    if not _attendre_local():
        _msg("NovaKit Online", "Le serveur local n'a pas démarré.")
        return 1

    print("Tunnel Cloudflare…")
    public = _tunnel()
    if not public:
        public = f"http://127.0.0.1:{PORT}"
        _msg(
            "NovaKit Online",
            "Tunnel public impossible — panel en local seulement.\n" + public,
        )
    else:
        sauver_creator({
            **charger_creator(),
            "online_api_url": public.rstrip("/"),
            "enabled": True,
        })
        URL_FILE.write_text(
            f"NovaKit — Système online\n"
            f"{'=' * 40}\n\n"
            f"Panel admin : {public}\n"
            f"API register : {public}/api/register\n\n"
            f"Compte : voir data/admin_credentials.txt\n"
            f"Laisse cette fenêtre OUVERTE pour rester en ligne.\n",
            encoding="utf-8",
        )

    if created and pwd:
        creds = f"Utilisateur : {user}\nMot de passe : {pwd}\n\n(aussi dans data/admin_credentials.txt)"
    else:
        creds = f"Utilisateur : {user}\nMot de passe : (celui déjà créé — voir data/admin_credentials.txt)"

    webbrowser.open(public if public.startswith("http") else f"http://127.0.0.1:{PORT}")
    _msg(
        "NovaKit Online — prêt",
        f"Système en ligne.\n\n{public}\n\n{creds}\n\n"
        "Laisse la console ouverte. Les installs apparaîtront dans le panel.",
    )

    print(f"\nAdmin : {public}")
    print(creds)
    print("\nCtrl+C pour arrêter.\n")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
