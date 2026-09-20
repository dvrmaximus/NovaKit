"""Configuration NovaKit — profil personnalisable (nom IA, clés, PIN…)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _app_root() -> Path:
    """Dossier de l'app (à côté de l'exe si packagée, sinon sources)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = _app_root()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
ENV_FILE = BASE_DIR / ".env"
SETUP_FLAG = DATA_DIR / "setup_done.flag"
KIT_VERSION = "1.1.0"


def resource_path(*parts: str) -> Path:
    """Fichier embarqué (exe) ou source."""
    rel = Path(*parts)
    candidates = [BASE_DIR / rel]
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / rel)
        candidates.append(BASE_DIR / "_internal" / rel)
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def bootstrap_app_files() -> None:
    """Copie creator.json / version.json à côté de l'exe au 1er lancement."""
    import shutil
    for name in ("creator.json", "version.json", ".env.example"):
        dest = BASE_DIR / name
        if dest.exists():
            continue
        src = resource_path(name)
        if src.exists() and src.resolve() != dest.resolve():
            try:
                shutil.copy2(src, dest)
            except Exception:
                pass


bootstrap_app_files()

load_dotenv(ENV_FILE)


def est_configure() -> bool:
    """True si le wizard a déjà été validé et qu'une clé API existe."""
    if not SETUP_FLAG.exists() or not ENV_FILE.exists():
        return False
    load_dotenv(ENV_FILE, override=True)
    cle = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(cle)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


API_KEY = _env("GEMINI_API_KEY")
_extra = _env("GEMINI_API_KEYS")
API_KEYS: list[str] = []
if API_KEY:
    API_KEYS.append(API_KEY)
for part in _extra.replace(";", ",").split(","):
    k = part.strip()
    if k and k not in API_KEYS:
        API_KEYS.append(k)
for i in range(2, 11):
    k = _env(f"GEMINI_API_KEY_{i}")
    if k and k not in API_KEYS:
        API_KEYS.append(k)

# Identité de l'assistant (choisie au setup)
NOM_IA = _env("NOM_IA", "Nova") or "Nova"
NOM_IA_AFFICHE = NOM_IA.upper()
MOT_MAGIQUE = (_env("MOT_MAGIQUE") or NOM_IA).lower()

VOIX_ASTAT = _env("VOIX_ASTAT", "fr-FR-DeniseNeural") or "fr-FR-DeniseNeural"
VOIX_RATE = _env("VOIX_RATE", "+20%") or "+20%"
VILLE_DEFAUT = _env("VILLE_DEFAUT", "Paris") or "Paris"
MODELE_GEMINI = _env("MODELE_GEMINI", "gemini-2.0-flash-lite") or "gemini-2.0-flash-lite"
REMOTE_PORT = int(_env("REMOTE_PORT", "8765") or "8765")
REMOTE_PIN = _env("REMOTE_PIN", "1234") or "1234"
NGROK_AUTHTOKEN = _env("NGROK_AUTHTOKEN")
NGROK_DOMAIN = _env("NGROK_DOMAIN")
ENABLE_TUNNEL = _env("ENABLE_TUNNEL", "true").lower() in ("1", "true", "yes", "oui")
TUNNEL_MODE = (_env("TUNNEL_MODE", "ngrok") or "ngrok").lower()
DESKTOP_MODE = _env("DESKTOP_MODE", "true").lower() in ("1", "true", "yes", "oui")

_mon_file = DATA_DIR / "desktop_monitor.txt"
if _mon_file.exists():
    DESKTOP_MONITOR = _mon_file.read_text(encoding="utf-8").strip() or "secondary"
else:
    DESKTOP_MONITOR = _env("DESKTOP_MONITOR", "secondary") or "secondary"

NOTES_FILE = DATA_DIR / "notes.json"
REMINDERS_FILE = DATA_DIR / "reminders.json"
HISTORY_FILE = DATA_DIR / "history.json"

KIT_NAME = "NovaKit"


def instructions_systeme() -> str:
    return f"""
Tu es {NOM_IA}, assistant Jarvis personnel. Français uniquement.
Tu peux DISCUTER naturellement (salutations, questions, blagues légères) ET exécuter des actions PC.
Réponses courtes : 1–3 phrases max. Pas de pavé.
Utilise tes outils pour heure/météo/apps/mails/PC/YouTube/Discord — n'invente pas de résultats d'outils.
« Connecte Gmail / Google » → connecter_gmail. « Connecte Discord » → connecter_discord.
YouTube avec recherche → ouvrir_youtube. Jeux / apps → ouvrir_application.
Discord : ouvrir liens ; messages webhook seulement si configuré (envoyer_webhook_discord).
Ne demande jamais de mot de passe Discord/Google dans le chat.
Confirme les actions en peu de mots ("Chrome ouvert.", "YouTube ouvert.").
Si on te parle sans ordre clair, réponds en conversation normale.
""".strip()


# Compat anciennes imports
INSTRUCTIONS_ASTAT = instructions_systeme()


def lire_profil() -> dict:
    """Lit le profil courant (.env + défauts)."""
    load_dotenv(ENV_FILE, override=True)
    return {
        "nom_ia": _env("NOM_IA", "Nova") or "Nova",
        "mot_magique": (_env("MOT_MAGIQUE") or _env("NOM_IA", "nova") or "nova").lower(),
        "api_key": _env("GEMINI_API_KEY"),
        "api_keys_extra": _env("GEMINI_API_KEYS"),
        "voix": _env("VOIX_ASTAT", "fr-FR-DeniseNeural") or "fr-FR-DeniseNeural",
        "voix_rate": _env("VOIX_RATE", "+20%") or "+20%",
        "modele": _env("MODELE_GEMINI", "gemini-2.0-flash-lite") or "gemini-2.0-flash-lite",
        "ville": _env("VILLE_DEFAUT", "Paris") or "Paris",
        "port": _env("REMOTE_PORT", "8765") or "8765",
        "pin": _env("REMOTE_PIN", "1234") or "1234",
        "enable_tunnel": "true" if _env("ENABLE_TUNNEL", "true").lower() in ("1", "true", "yes", "oui") else "false",
        "tunnel_mode": (_env("TUNNEL_MODE", "ngrok") or "ngrok").lower(),
        "ngrok_token": _env("NGROK_AUTHTOKEN"),
        "ngrok_domain": _env("NGROK_DOMAIN"),
        "desktop_mode": "true" if _env("DESKTOP_MODE", "true").lower() in ("1", "true", "yes", "oui") else "false",
        "desktop_monitor": _env("DESKTOP_MONITOR", "secondary") or "secondary",
        "email": _env("USER_EMAIL"),
        "pseudo": _env("USER_PSEUDO"),
        "backup_daily": "true" if _env("BACKUP_DAILY", "true").lower() in ("1", "true", "yes", "oui") else "false",
        "couleur_ia": _env("COULEUR_IA", "#4EC9D4") or "#4EC9D4",
        "accent_hex": _env("COULEUR_IA", "#4EC9D4") or "#4EC9D4",
        "accent_intensite": _env("ACCENT_INTENSITE", "1.0") or "1.0",
        "discord_webhook": _env("DISCORD_WEBHOOK"),
    }


def ecrire_profil(valeurs: dict) -> None:
    """Écrit le .env + drapeau setup depuis le wizard / paramètres."""
    actuel = lire_profil() if ENV_FILE.exists() else {}
    merged = {**actuel, **{k: v for k, v in valeurs.items() if v is not None}}
    lignes = [
        f"# Profil {KIT_NAME} — généré automatiquement",
        f"NOM_IA={merged.get('nom_ia', 'Nova')}",
        f"MOT_MAGIQUE={merged.get('mot_magique', merged.get('nom_ia', 'nova')).lower()}",
        f"GEMINI_API_KEY={merged.get('api_key', '')}",
        f"GEMINI_API_KEYS={merged.get('api_keys_extra', '')}",
        f"VOIX_ASTAT={merged.get('voix', 'fr-FR-DeniseNeural')}",
        f"VOIX_RATE={merged.get('voix_rate', '+20%')}",
        f"MODELE_GEMINI={merged.get('modele', 'gemini-2.0-flash-lite')}",
        f"VILLE_DEFAUT={merged.get('ville', 'Paris')}",
        f"REMOTE_PORT={merged.get('port', '8765')}",
        f"REMOTE_PIN={merged.get('pin', '1234')}",
        f"ENABLE_TUNNEL={merged.get('enable_tunnel', 'true')}",
        f"TUNNEL_MODE={merged.get('tunnel_mode', 'ngrok')}",
        f"NGROK_AUTHTOKEN={merged.get('ngrok_token', '')}",
        f"NGROK_DOMAIN={merged.get('ngrok_domain', '')}",
        f"DESKTOP_MODE={merged.get('desktop_mode', 'true')}",
        f"DESKTOP_MONITOR={merged.get('desktop_monitor', 'secondary')}",
        f"USER_EMAIL={merged.get('email', '')}",
        f"USER_PSEUDO={merged.get('pseudo', '')}",
        f"BACKUP_DAILY={merged.get('backup_daily', 'true')}",
        f"COULEUR_IA={merged.get('couleur_ia') or merged.get('accent_hex') or '#4EC9D4'}",
        f"ACCENT_INTENSITE={merged.get('accent_intensite', '1.0')}",
        f"DISCORD_WEBHOOK={merged.get('discord_webhook', '')}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lignes), encoding="utf-8")
    SETUP_FLAG.write_text("ok", encoding="utf-8")
    mon = str(merged.get("desktop_monitor") or "secondary")
    try:
        (DATA_DIR / "desktop_monitor.txt").write_text(mon, encoding="utf-8")
    except Exception:
        pass
    recharger_globals()


def recharger_globals() -> None:
    """Recharge les variables module depuis le .env."""
    load_dotenv(ENV_FILE, override=True)
    global API_KEY, API_KEYS, NOM_IA, NOM_IA_AFFICHE, MOT_MAGIQUE
    global VOIX_ASTAT, VOIX_RATE, VILLE_DEFAUT, MODELE_GEMINI
    global REMOTE_PIN, REMOTE_PORT, ENABLE_TUNNEL, TUNNEL_MODE
    global DESKTOP_MODE, DESKTOP_MONITOR, INSTRUCTIONS_ASTAT
    global NGROK_AUTHTOKEN, NGROK_DOMAIN, USER_EMAIL, USER_PSEUDO, BACKUP_DAILY
    global DISCORD_WEBHOOK
    API_KEY = _env("GEMINI_API_KEY")
    API_KEYS = [API_KEY] if API_KEY else []
    for part in _env("GEMINI_API_KEYS").replace(";", ",").split(","):
        k = part.strip()
        if k and k not in API_KEYS:
            API_KEYS.append(k)
    NOM_IA = _env("NOM_IA", "Nova") or "Nova"
    NOM_IA_AFFICHE = NOM_IA.upper()
    MOT_MAGIQUE = (_env("MOT_MAGIQUE") or NOM_IA).lower()
    VOIX_ASTAT = _env("VOIX_ASTAT", "fr-FR-DeniseNeural") or "fr-FR-DeniseNeural"
    VOIX_RATE = _env("VOIX_RATE", "+20%") or "+20%"
    VILLE_DEFAUT = _env("VILLE_DEFAUT", "Paris") or "Paris"
    MODELE_GEMINI = _env("MODELE_GEMINI", "gemini-2.0-flash-lite") or "gemini-2.0-flash-lite"
    try:
        REMOTE_PORT = int(_env("REMOTE_PORT", "8765") or "8765")
    except ValueError:
        REMOTE_PORT = 8765
    REMOTE_PIN = _env("REMOTE_PIN", "1234") or "1234"
    ENABLE_TUNNEL = _env("ENABLE_TUNNEL", "true").lower() in ("1", "true", "yes", "oui")
    TUNNEL_MODE = (_env("TUNNEL_MODE", "ngrok") or "ngrok").lower()
    NGROK_AUTHTOKEN = _env("NGROK_AUTHTOKEN")
    NGROK_DOMAIN = _env("NGROK_DOMAIN")
    DESKTOP_MODE = _env("DESKTOP_MODE", "true").lower() in ("1", "true", "yes", "oui")
    _mon_file = DATA_DIR / "desktop_monitor.txt"
    if _mon_file.exists():
        DESKTOP_MONITOR = _mon_file.read_text(encoding="utf-8").strip() or "secondary"
    else:
        DESKTOP_MONITOR = _env("DESKTOP_MONITOR", "secondary") or "secondary"
    USER_EMAIL = _env("USER_EMAIL")
    USER_PSEUDO = _env("USER_PSEUDO")
    BACKUP_DAILY = _env("BACKUP_DAILY", "true").lower() in ("1", "true", "yes", "oui")
    DISCORD_WEBHOOK = _env("DISCORD_WEBHOOK")
    INSTRUCTIONS_ASTAT = instructions_systeme()


# Init vars email / backup
USER_EMAIL = _env("USER_EMAIL")
USER_PSEUDO = _env("USER_PSEUDO")
BACKUP_DAILY = _env("BACKUP_DAILY", "true").lower() in ("1", "true", "yes", "oui")
DISCORD_WEBHOOK = _env("DISCORD_WEBHOOK")
