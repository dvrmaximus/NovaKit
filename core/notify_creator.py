"""Inscriptions simples → Formspree (mail) ou Discord."""

from __future__ import annotations

import json
import platform
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from config import BASE_DIR, DATA_DIR, KIT_NAME, KIT_VERSION

CREATOR_FILE = BASE_DIR / "creator.json"
INSTALLS_LOG = DATA_DIR / "installs_sent.jsonl"


def charger_creator() -> dict:
    if not CREATOR_FILE.exists():
        return {"enabled": False}
    try:
        data = json.loads(CREATOR_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"enabled": False}
    except Exception:
        return {"enabled": False}


def sauver_creator(data: dict) -> None:
    actuel = charger_creator()
    actuel.update(data)
    actuel.pop("_aide", None)
    CREATOR_FILE.write_text(json.dumps(actuel, ensure_ascii=False, indent=2), encoding="utf-8")


def _payload(profil: dict) -> dict:
    return {
        "kit": KIT_NAME,
        "version": KIT_VERSION,
        "event": "inscription",
        "when": datetime.now(timezone.utc).isoformat(),
        "pseudo": (profil.get("pseudo") or "Anonyme")[:64],
        "nom_ia": (profil.get("nom_ia") or "?")[:64],
        "ville": (profil.get("ville") or "")[:64],
        "os": platform.system(),
        "pc": platform.node()[:48],
    }


def _journaliser(data: dict, ok: bool, detail: str = ""):
    INSTALLS_LOG.parent.mkdir(exist_ok=True)
    with INSTALLS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**data, "ok": ok, "detail": detail}, ensure_ascii=False) + "\n")


def _post_form(url: str, fields: dict) -> None:
    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": f"{KIT_NAME}/{KIT_VERSION}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"HTTP {resp.status}")


def _post_json(url: str, data: dict) -> None:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": f"{KIT_NAME}/{KIT_VERSION}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if getattr(resp, "status", 200) >= 400:
            raise RuntimeError(f"HTTP {resp.status}")


def notifier_setup(profil: dict) -> None:
    threading.Thread(target=_notifier_sync, args=(profil,), daemon=True).start()


def _notifier_sync(profil: dict):
    cfg = charger_creator()
    data = _payload(profil)
    if not cfg.get("enabled", True):
        _journaliser(data, False, "off")
        return

    form = (cfg.get("inscription_email_form") or cfg.get("formspree") or cfg.get("notify_url") or "").strip()
    webhook = (cfg.get("discord_webhook") or "").strip()
    ok = False
    detail = []

    try:
        if form.startswith("https://"):
            # Formspree / Getform / etc. → arrive dans ta boîte mail
            _post_form(form, {
                "name": data["pseudo"],
                "pseudo": data["pseudo"],
                "nom_ia": data["nom_ia"],
                "ville": data["ville"],
                "kit": data["kit"],
                "version": data["version"],
                "pc": f"{data['os']} {data['pc']}",
                "_subject": f"[{KIT_NAME}] {data['pseudo']} → {data['nom_ia']}",
                "message": (
                    f"{data['pseudo']} a installé {KIT_NAME}.\n"
                    f"IA : {data['nom_ia']}\nVille : {data['ville']}\n"
                    f"PC : {data['os']} / {data['pc']}"
                ),
            })
            ok = True
            detail.append("mail")
        if webhook.startswith("https://discord.com/api/webhooks") or webhook.startswith("https://discordapp.com/api/webhooks"):
            _post_json(webhook, {
                "content": (
                    f"**{data['pseudo']}** a installé **{data['nom_ia']}** "
                    f"({data['ville'] or '—'}) · {data['os']}"
                )
            })
            ok = True
            detail.append("discord")
        if not form and not webhook:
            detail.append("pas_de_lien")
    except Exception as exc:
        detail.append(f"err:{exc}")

    _journaliser(data, ok, "+".join(detail) if detail else "")
