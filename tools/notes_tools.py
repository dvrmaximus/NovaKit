import json
from datetime import datetime

from config import NOTES_FILE


def _charger_notes():
    if NOTES_FILE.exists():
        return json.loads(NOTES_FILE.read_text(encoding="utf-8"))
    return []


def _sauver_notes(notes):
    NOTES_FILE.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")


def ajouter_note(contenu: str) -> str:
    """Ajoute une note personnelle.

    Args:
        contenu: le texte de la note à enregistrer
    """
    notes = _charger_notes()
    notes.append({"date": datetime.now().isoformat(), "contenu": contenu.strip()})
    _sauver_notes(notes)
    return f"Note enregistrée : « {contenu[:60]}{'…' if len(contenu) > 60 else ''} »"


def lire_notes() -> str:
    """Lit toutes les notes enregistrées."""
    notes = _charger_notes()
    if not notes:
        return "Tu n'as aucune note enregistrée."
    lignes = []
    for i, note in enumerate(notes[-10:], 1):
        date = note["date"][:16].replace("T", " ")
        lignes.append(f"{i}. [{date}] {note['contenu']}")
    return "\n".join(lignes)
