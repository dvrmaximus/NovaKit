import json
import threading
from datetime import datetime, timedelta

from config import REMINDERS_FILE

_rappels_actifs = []


def _charger():
    if REMINDERS_FILE.exists():
        return json.loads(REMINDERS_FILE.read_text(encoding="utf-8"))
    return []


def _sauver(rappels):
    REMINDERS_FILE.write_text(json.dumps(rappels, ensure_ascii=False, indent=2), encoding="utf-8")


def _declencher(message: str):
    try:
        import winsound
        winsound.MessageBeep()
    except Exception:
        pass
    print(f"\n🔔 RAPPEL ASTAT : {message}\n")


def creer_rappel(message: str, dans_minutes: int = 5) -> str:
    """Crée un rappel qui sonnera après un délai.

    Args:
        message: ce dont tu veux te rappeler
        dans_minutes: délai en minutes (5 par défaut)
    """
    dans_minutes = max(1, int(dans_minutes))
    echeance = datetime.now() + timedelta(minutes=dans_minutes)
    rappels = _charger()
    rappels.append({
        "message": message.strip(),
        "echeance": echeance.isoformat(),
        "fait": False,
    })
    _sauver(rappels)

    timer = threading.Timer(dans_minutes * 60, _declencher, args=[message])
    timer.daemon = True
    timer.start()
    _rappels_actifs.append(timer)

    return f"Rappel programmé dans {dans_minutes} min : « {message} »"


def lister_rappels() -> str:
    """Liste les rappels en attente."""
    rappels = [r for r in _charger() if not r.get("fait")]
    if not rappels:
        return "Aucun rappel en attente."
    lignes = []
    for i, r in enumerate(rappels, 1):
        echeance = r["echeance"][:16].replace("T", " ")
        lignes.append(f"{i}. [{echeance}] {r['message']}")
    return "\n".join(lignes)
