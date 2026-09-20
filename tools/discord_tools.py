"""Discord — ouverture app/URL + webhook optionnel (pas de mot de passe)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import os

from config import DATA_DIR, ENV_FILE


def _webhook_url() -> str:
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_FILE, override=True)
    except Exception:
        pass
    return (os.getenv("DISCORD_WEBHOOK") or "").strip()


def _flag_connecte() -> Path:
    return DATA_DIR / "discord_connect.flag"


def connecter_discord() -> str:
    """Ouvre Discord (app si possible, sinon navigateur) pour se connecter."""
    try:
        from tools.system_tools import ouvrir_application
        msg = ouvrir_application("discord")
        if "ouvert" in msg.lower() and "ne trouve pas" not in msg.lower():
            try:
                _flag_connecte().write_text("1", encoding="utf-8")
            except Exception:
                pass
            return "Discord ouvert. Connecte-toi si besoin."
    except Exception:
        pass

    for url in ("discord://", "https://discord.com/app", "https://discord.com/login"):
        try:
            webbrowser.open(url)
            try:
                _flag_connecte().write_text("1", encoding="utf-8")
            except Exception:
                pass
            return "J'ouvre Discord dans le navigateur. Connecte-toi avec ton compte."
        except Exception:
            continue
    return "Impossible d'ouvrir Discord. Lance-le depuis le menu Démarrer."


def ouvrir_lien_discord(url: str) -> str:
    """Ouvre une invite, un salon ou un DM Discord (lien fourni par l'utilisateur)."""
    u = (url or "").strip()
    if not u:
        return "Donne-moi un lien Discord (invite ou salon)."
    if not u.startswith("http"):
        if u.startswith("discord.com") or u.startswith("discord.gg"):
            u = "https://" + u
        else:
            return "Lien Discord invalide. Exemple : https://discord.gg/…"
    ok = ("discord.com" in u) or ("discord.gg" in u) or u.startswith("discord://")
    if not ok:
        return "Ce n'est pas un lien Discord."
    webbrowser.open(u)
    return "J'ouvre ce lien Discord."


def envoyer_webhook_discord(message: str) -> str:
    """Envoie un message via le webhook configuré dans les paramètres (DISCORD_WEBHOOK)."""
    webhook = _webhook_url()
    if not webhook:
        return (
            "Aucun webhook Discord. "
            "Ajoute-le dans Paramètres > Connexions "
            "(URL du type discord.com/api/webhooks/...)."
        )
    if not (
        webhook.startswith("https://discord.com/api/webhooks")
        or webhook.startswith("https://discordapp.com/api/webhooks")
    ):
        return "URL webhook Discord invalide."

    texte = (message or "").strip()
    if not texte:
        return "Dis-moi quoi envoyer sur Discord."
    if len(texte) > 1900:
        texte = texte[:1900] + "…"

    payload = json.dumps({"content": texte}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "NovaKit"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            if 200 <= getattr(resp, "status", 200) < 300:
                return "Message envoyé sur Discord."
            return f"Discord a répondu {getattr(resp, 'status', '?')}."
    except urllib.error.HTTPError as exc:
        return f"Échec webhook Discord ({exc.code}). Vérifie l'URL dans les paramètres."
    except Exception as exc:
        return f"Envoi Discord impossible : {exc}"
