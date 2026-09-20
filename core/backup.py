"""Sauvegarde ZIP du profil (quotidienne + export / restauration)."""

from __future__ import annotations

import json
import shutil
import threading
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from config import BASE_DIR, DATA_DIR, ENV_FILE, KIT_NAME, KIT_VERSION, lire_profil

BACKUP_DIR = DATA_DIR / "backups"
STATE_FILE = DATA_DIR / "backup_state.json"
KEEP_DAYS = 14

_DATA_FILES = (
    "notes.json",
    "history.json",
    "reminders.json",
    "setup_done.flag",
    "desktop_monitor.txt",
    "gmail_token.json",
    "backup_state.json",
    "online.db",
    "admin_credentials.txt",
    "url_mobile.txt",
    "url_admin_online.txt",
)


def backup_active() -> bool:
    return (lire_profil().get("backup_daily") or "true") == "true"


def _state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def derniere_sauvegarde() -> str | None:
    return _state().get("last_date")


def besoin_sauvegarde_du_jour() -> bool:
    if not backup_active():
        return False
    return derniere_sauvegarde() != date.today().isoformat()


def _purge_anciennes() -> None:
    if not BACKUP_DIR.exists():
        return
    zips = sorted(BACKUP_DIR.glob("novakit_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for ancien in zips[KEEP_DAYS:]:
        try:
            ancien.unlink()
        except Exception:
            pass


def _fichiers_racine_identite() -> list[Path]:
    fichiers = []
    for name in ("creator.json", "token.json", "credentials.json"):
        p = BASE_DIR / name
        if p.exists():
            fichiers.append(p)
    fichiers.extend(BASE_DIR.glob("client_secret*.json"))
    return fichiers


def creer_sauvegarde(raison: str = "manual", dest: Path | None = None) -> Path:
    """
    Crée une archive ZIP complète du compte :
    .env, data (notes, Gmail, etc.), creator.json, secrets locaux.
    """
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out = Path(dest) if dest else (BACKUP_DIR / f"novakit_{stamp}.zip")
    out.parent.mkdir(parents=True, exist_ok=True)

    profil = lire_profil()
    email = (profil.get("email") or "").strip()
    pseudo = profil.get("pseudo") or profil.get("nom_ia") or "Nova"

    meta = {
        "kit": KIT_NAME,
        "version": KIT_VERSION,
        "when": datetime.now(timezone.utc).isoformat(),
        "raison": raison,
        "email": email,
        "pseudo": pseudo,
        "pc": __import__("platform").node()[:48],
    }

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        if ENV_FILE.exists():
            zf.write(ENV_FILE, arcname="profil.env")
        for name in _DATA_FILES:
            src = DATA_DIR / name
            if src.exists() and src.is_file():
                zf.write(src, arcname=f"data/{name}")
        for src in _fichiers_racine_identite():
            zf.write(src, arcname=f"root/{src.name}")

    if dest is None:
        st = _state()
        st["last_date"] = date.today().isoformat()
        st["last_file"] = out.name
        st["last_raison"] = raison
        st["email"] = email
        _save_state(st)
        _purge_anciennes()
        jour = BACKUP_DIR / f"latest_{date.today().isoformat()}.zip"
        try:
            shutil.copy2(out, jour)
        except Exception:
            pass

    return out


def exporter_zip_bureau() -> Path:
    """Copie une sauvegarde ZIP complète sur le Bureau."""
    bureau = Path.home() / "Desktop"
    if not bureau.exists():
        bureau = Path.home() / "OneDrive" / "Desktop"
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    dest = bureau / f"NovaKit_sauvegarde_{stamp}.zip"
    return creer_sauvegarde("export_bureau", dest=dest)


def restaurer_sauvegarde(zip_path: Path | str) -> None:
    """Restaure le compte depuis un ZIP (profil + data + Gmail)."""
    path = Path(zip_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    DATA_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            data = zf.read(info)
            if name == "profil.env":
                ENV_FILE.write_bytes(data)
            elif name.startswith("data/") and "/" in name:
                dest = DATA_DIR / Path(name).name
                dest.write_bytes(data)
            elif name.startswith("root/"):
                dest = BASE_DIR / Path(name).name
                dest.write_bytes(data)
    # Assure le flag setup
    flag = DATA_DIR / "setup_done.flag"
    if ENV_FILE.exists() and not flag.exists():
        flag.write_text("ok", encoding="utf-8")


def lister_sauvegardes(limit: int = 20) -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    items = []
    for p in sorted(BACKUP_DIR.glob("novakit_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        items.append({
            "name": p.name,
            "path": str(p),
            "size_ko": round(p.stat().st_size / 1024, 1),
            "when": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds"),
        })
    return items


def verifier_sauvegarde_quotidienne(async_: bool = True) -> None:
    if not besoin_sauvegarde_du_jour():
        return

    def _run():
        try:
            creer_sauvegarde("daily")
        except Exception as exc:
            print(f"[backup] {exc}")

    if async_:
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()
