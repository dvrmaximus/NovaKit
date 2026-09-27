"""Bus d'evenements pour basculer les vues Performance / Gaming dans Astat."""

from __future__ import annotations

from typing import Callable

# actions: "open_perf" | "open_gaming" | "close_all" | "focus_perf" | "focus_gaming"
_listeners: list[Callable[[str], None]] = []


def on_panel_request(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def request(action: str) -> str:
    """Demande UI (voix / commandes). Retourne un message FR."""
    action = (action or "").strip().lower()
    aliases = {
        "perf": "open_perf",
        "performance": "open_perf",
        "ouvre_perf": "open_perf",
        "ouvre_performance": "open_perf",
        "gaming": "open_gaming",
        "game": "open_gaming",
        "jeu": "open_gaming",
        "ouvre_gaming": "open_gaming",
        "ferme": "close_all",
        "fermer": "close_all",
        "close": "close_all",
        "close_all": "close_all",
        "ferme_panneaux": "close_all",
    }
    action = aliases.get(action, action)
    if action not in ("open_perf", "open_gaming", "close_all", "focus_perf", "focus_gaming"):
        return "Vue inconnue."
    for cb in list(_listeners):
        try:
            cb(action)
        except Exception:
            pass
    if action == "open_perf" or action == "focus_perf":
        return "Vue Performance dans Astat."
    if action == "open_gaming" or action == "focus_gaming":
        return "Vue Gaming dans Astat."
    return "Retour mode Assist."
