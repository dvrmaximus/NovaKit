"""Etat des modes HUD (Assist / Performance / Gaming) — partage UI + voix."""

from __future__ import annotations

from typing import Callable

MODES = ("assist", "performance", "gaming")
LABELS = {
    "assist": "Assist",
    "performance": "Performance",
    "gaming": "Gaming",
}

_mode = "assist"
_listeners: list[Callable[[str], None]] = []


def normaliser_mode(valeur: str | None) -> str:
    t = (valeur or "").strip().lower()
    aliases = {
        "normal": "assist",
        "aide": "assist",
        "assistant": "assist",
        "default": "assist",
        "perf": "performance",
        "perfs": "performance",
        "system": "performance",
        "systeme": "performance",
        "game": "gaming",
        "jeu": "gaming",
        "jeux": "gaming",
    }
    t = aliases.get(t, t)
    return t if t in MODES else "assist"


def get_mode() -> str:
    return _mode


def on_mode_change(callback: Callable[[str], None]) -> None:
    if callback not in _listeners:
        _listeners.append(callback)


def set_mode(mode: str, *, persist: bool = True, announce: bool = True) -> str:
    """Change le mode HUD. Retourne un message FR pour la voix/chat."""
    global _mode
    cible = normaliser_mode(mode)
    changed = cible != _mode
    _mode = cible
    if persist:
        _persister(cible)
    if changed:
        for cb in list(_listeners):
            try:
                cb(cible)
            except Exception:
                pass
    label = LABELS.get(cible, cible)
    if announce:
        if cible == "assist":
            return f"Mode {label} : journal et commandes."
        if cible == "performance":
            return f"Mode {label} : centre telemetrie ouvert (CPU, RAM, GPU)."
        return f"Mode {label} : centre gaming ouvert (FPS, presets, bench)."
    return label


def _persister(mode: str) -> None:
    try:
        from config import ecrire_profil, lire_profil

        actuel = lire_profil()
        if actuel.get("mode_hud") == mode:
            return
        ecrire_profil({"mode_hud": mode})
    except Exception:
        pass


def charger_depuis_profil() -> str:
    try:
        from config import lire_profil

        return set_mode(lire_profil().get("mode_hud") or "assist", persist=False, announce=False)
    except Exception:
        return set_mode("assist", persist=False, announce=False)
