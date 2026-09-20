"""Mise à jour automatique NovaKit (zip distant + version.json).

Conserve TOUJOURS le profil utilisateur (.env, data, Gmail, etc.)
pour ne jamais forcer une reconnexion après une MAJ.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from config import BASE_DIR, DATA_DIR, ENV_FILE, KIT_VERSION, SETUP_FLAG

VERSION_FILE = BASE_DIR / "version.json"

# Dossiers / fichiers jamais écrasés par une MAJ
PRESERVE_NAMES = {
    ".env",
    "creator.json",
    "data",
    "token.json",
    "credentials.json",
    "bin",  # cloudflared téléchargé localement
}

PRESERVE_GLOBS = (
    "client_secret*.json",
    "*.lnk",
)


def version_locale() -> str:
    if VERSION_FILE.exists():
        try:
            return str(json.loads(VERSION_FILE.read_text(encoding="utf-8")).get("version") or KIT_VERSION)
        except Exception:
            pass
    return KIT_VERSION


def _parse(v: str) -> tuple:
    parts = []
    for p in (v or "0").strip().lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def est_plus_recente(remote: str, local: str) -> bool:
    return _parse(remote) > _parse(local)


def _charger_update_url() -> str:
    try:
        from core.notify_creator import charger_creator
        return (charger_creator().get("update_check_url") or "").strip()
    except Exception:
        return ""


def verifier_mise_a_jour() -> dict | None:
    """Retourne {version, zip_url, notes} si une MAJ existe, sinon None."""
    url = _charger_update_url()
    if not url.startswith("https://"):
        return None
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    remote_v = str(info.get("version") or "")
    zip_url = str(info.get("zip_url") or "").strip()
    if not remote_v or not zip_url.startswith("https://"):
        return None
    if not est_plus_recente(remote_v, version_locale()):
        return None
    return {
        "version": remote_v,
        "zip_url": zip_url,
        "notes": str(info.get("notes") or ""),
        "local": version_locale(),
    }


def _doit_preserver(name: str) -> bool:
    if name in PRESERVE_NAMES:
        return True
    if name.startswith(".") and name not in (".gitignore", ".env.example", ".gitattributes"):
        # .env, .venv, etc. — on ne touche pas
        if name in (".env", ".venv"):
            return True
        if name == ".env":
            return True
    for pattern in PRESERVE_GLOBS:
        if Path(name).match(pattern):
            return True
    return False


def _snapshot_avant_maj() -> Path | None:
    """ZIP de sécurité du profil juste avant la MAJ."""
    try:
        from core.backup import creer_sauvegarde
        return creer_sauvegarde("pre_update")
    except Exception as exc:
        print(f"[update] snapshot: {exc}")
        return None


def _restaurer_profil_si_perdu(snapshot: Path | None) -> None:
    """Si la MAJ a mangé .env / setup → restaure depuis le ZIP de sécurité."""
    perdu = not ENV_FILE.exists() or not SETUP_FLAG.exists()
    if not perdu:
        # Migre token Gmail racine → data si besoin
        legacy = BASE_DIR / "token.json"
        dest = DATA_DIR / "gmail_token.json"
        if legacy.exists() and not dest.exists():
            try:
                DATA_DIR.mkdir(exist_ok=True)
                shutil.copy2(legacy, dest)
            except Exception:
                pass
        return
    if not snapshot or not Path(snapshot).exists():
        return
    try:
        from core.backup import restaurer_sauvegarde
        restaurer_sauvegarde(snapshot)
        print("[update] profil restauré depuis snapshot ZIP")
    except Exception as exc:
        print(f"[update] restauration profil: {exc}")


def appliquer_mise_a_jour(info: dict, on_progress=None) -> str:
    """
    Télécharge le zip, remplace le code, GARDE le compte / Gmail / data.
    """
    zip_url = info["zip_url"]
    tmp_dir = Path(tempfile.mkdtemp(prefix="novakit_upd_"))
    zip_path = tmp_dir / "update.zip"

    def prog(msg: str):
        if on_progress:
            try:
                on_progress(msg)
            except Exception:
                pass

    prog("Sauvegarde profil…")
    snapshot = _snapshot_avant_maj()

    # Mémorise les chemins utilisateur à protéger absolument
    garde_env = ENV_FILE.read_bytes() if ENV_FILE.exists() else None
    garde_creator = None
    creator = BASE_DIR / "creator.json"
    if creator.exists():
        garde_creator = creator.read_bytes()

    prog("Téléchargement…")
    urllib.request.urlretrieve(zip_url, zip_path)

    prog("Extraction…")
    extract_dir = tmp_dir / "extract"
    extract_dir.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    racines = [p for p in extract_dir.iterdir() if p.is_dir()]
    source = racines[0] if len(racines) == 1 else extract_dir

    prog("Installation (compte conservé)…")
    for item in source.iterdir():
        name = item.name
        if _doit_preserver(name):
            continue
        # Ne jamais écraser le dossier data même s'il arrive dans le zip
        if name.lower() == "data":
            continue
        dest = BASE_DIR / name
        try:
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except Exception as exc:
            print(f"[update] skip {name}: {exc}")

    # Réécrit toujours le profil utilisateur s'il existait
    if garde_env is not None:
        ENV_FILE.write_bytes(garde_env)
    if garde_creator is not None:
        creator.write_bytes(garde_creator)
    if not SETUP_FLAG.exists() and garde_env is not None:
        SETUP_FLAG.parent.mkdir(exist_ok=True)
        SETUP_FLAG.write_text("ok", encoding="utf-8")

    _restaurer_profil_si_perdu(snapshot)

    (BASE_DIR / "version.json").write_text(
        json.dumps({
            "version": info["version"],
            "zip_url": info.get("zip_url", ""),
            "notes": info.get("notes", ""),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    prog("OK")
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    return str(BASE_DIR)


def verifier_en_arriere_plan(callback):
    def _run():
        try:
            info = verifier_mise_a_jour()
        except Exception:
            info = None
        try:
            callback(info)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
