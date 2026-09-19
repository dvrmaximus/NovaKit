"""Mise à jour automatique NovaKit (zip distant + version.json)."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from config import BASE_DIR, DATA_DIR, KIT_VERSION

VERSION_FILE = BASE_DIR / "version.json"
PRESERVE = {".env", "creator.json", "data"}


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
    """
    Retourne {version, zip_url, notes} si une MAJ existe, sinon None.
    """
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


def appliquer_mise_a_jour(info: dict, on_progress=None) -> str:
    """
    Télécharge le zip, remplace les fichiers (garde .env + data + creator.json).
    Retourne le chemin du dossier.
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

    prog("Téléchargement…")
    urllib.request.urlretrieve(zip_url, zip_path)

    prog("Extraction…")
    extract_dir = tmp_dir / "extract"
    extract_dir.mkdir()
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # Zip GitHub = un sous-dossier racine
    racines = [p for p in extract_dir.iterdir() if p.is_dir()]
    source = racines[0] if len(racines) == 1 else extract_dir

    prog("Installation…")
    for item in source.iterdir():
        name = item.name
        if name in PRESERVE or name.startswith("."):
            # On permet de mettre à jour .gitignore etc., mais pas .env
            if name == ".env" or name == "creator.json":
                continue
            if name == "data":
                continue
        dest = BASE_DIR / name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Toujours écrire version.json à jour
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
    """callback(info|None) sur le thread appelant via… le callback est appelé depuis le thread."""
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
