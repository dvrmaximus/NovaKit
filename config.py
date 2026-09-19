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
Utilise tes outils pour heure/météo/apps/mails/PC — n'invente pas de résultats d'outils.
Pour ouvrir une app : outil ouvrir_application avec le nom exact.
Confirme les actions en peu de mots ("Chrome ouvert.").
Si on te parle sans ordre clair, réponds en conversation normale.
""".strip()


# Compat anciennes imports
INSTRUCTIONS_ASTAT = instructions_systeme()


def ecrire_profil(valeurs: dict) -> None:
    """Écrit le .env + drapeau setup depuis le wizard."""
    lignes = [
        f"# Profil {KIT_NAME} — généré automatiquement",
        f"NOM_IA={valeurs.get('nom_ia', 'Nova')}",
        f"MOT_MAGIQUE={valeurs.get('mot_magique', valeurs.get('nom_ia', 'nova')).lower()}",
        f"GEMINI_API_KEY={valeurs.get('api_key', '')}",
        f"GEMINI_API_KEYS={valeurs.get('api_keys_extra', '')}",
        f"VOIX_ASTAT={valeurs.get('voix', 'fr-FR-DeniseNeural')}",
        f"VOIX_RATE={valeurs.get('voix_rate', '+20%')}",
        f"MODELE_GEMINI={valeurs.get('modele', 'gemini-2.0-flash-lite')}",
        f"VILLE_DEFAUT={valeurs.get('ville', 'Paris')}",
        f"REMOTE_PORT={valeurs.get('port', '8765')}",
        f"REMOTE_PIN={valeurs.get('pin', '1234')}",
        f"ENABLE_TUNNEL={valeurs.get('enable_tunnel', 'true')}",
        f"TUNNEL_MODE={valeurs.get('tunnel_mode', 'ngrok')}",
        f"NGROK_AUTHTOKEN={valeurs.get('ngrok_token', '')}",
        f"NGROK_DOMAIN={valeurs.get('ngrok_domain', '')}",
        f"DESKTOP_MODE={valeurs.get('desktop_mode', 'true')}",
        f"DESKTOP_MONITOR={valeurs.get('desktop_monitor', 'secondary')}",
        "",
    ]
    ENV_FILE.write_text("\n".join(lignes), encoding="utf-8")
    SETUP_FLAG.write_text("ok", encoding="utf-8")
    load_dotenv(ENV_FILE, override=True)
    # Recharge les globals critiques
    global API_KEY, API_KEYS, NOM_IA, NOM_IA_AFFICHE, MOT_MAGIQUE
    global VOIX_ASTAT, VILLE_DEFAUT, REMOTE_PIN, INSTRUCTIONS_ASTAT
    API_KEY = _env("GEMINI_API_KEY")
    API_KEYS = [API_KEY] if API_KEY else []
    NOM_IA = _env("NOM_IA", "Nova") or "Nova"
    NOM_IA_AFFICHE = NOM_IA.upper()
    MOT_MAGIQUE = (_env("MOT_MAGIQUE") or NOM_IA).lower()
    VOIX_ASTAT = _env("VOIX_ASTAT", "fr-FR-DeniseNeural")
    VILLE_DEFAUT = _env("VILLE_DEFAUT", "Paris")
    REMOTE_PIN = _env("REMOTE_PIN", "1234")
    INSTRUCTIONS_ASTAT = instructions_systeme()
