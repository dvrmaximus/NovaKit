# Palette NovaKit — HUD futuriste (graphite / navy + accent utilisateur)

from __future__ import annotations

import re

BG_VOID = "#07090E"
BG_DEEP = "#0B0E14"
BG_MAIN = "#10141C"
BG_PANEL = "#151A24"
BG_PANEL2 = "#1A2130"
BG_INPUT = "#0F131B"
ACCENT = "#4EC9D4"
ACCENT_SOFT = "#7AD4DC"
ACCENT_DIM = "#1A4A52"
ACCENT_GLOW = "#0F2A30"
ACCENT_HOT = "#A8EEF2"
ACCENT_WARN = "#C4A574"
ACCENT_DANGER = "#B86B6B"
TEXT_PRIMARY = "#E8EEF5"
TEXT_SECONDARY = "#9AA8B8"
TEXT_MUTED = "#5C6A7A"
LINE = "#1E2736"
LINE_BRIGHT = "#2A3648"
BUBBLE_USER = "#1A2130"
BUBBLE_ASTAT = "#121820"
SUCCESS = "#6BB89A"

VERSION = "5.1"

GLASS = "#121820"
GLASS2 = "#1A2130"
GLASS_BORDER = "#243044"
GLASS_BORDER_HOT = "#3A4E68"

FONT_MONO = "Cascadia Mono"
FONT_MONO_FALLBACK = "Consolas"
FONT_UI = "Segoe UI Variable"

# Intensité 0.55–1.0 appliquée sur l'accent de base
ACCENT_INTENSITY = 1.0
_ACCENT_BASE = "#4EC9D4"

PRESETS_COULEUR = [
    ("Cyan", "#4EC9D4"),
    ("Bleu", "#5B9CF5"),
    ("Vert", "#4FD6A0"),
    ("Ambre", "#E0B35A"),
    ("Magenta", "#D45BA8"),
    ("Rouge", "#E25B6A"),
    ("Violet", "#9B7BE8"),
    ("Blanc", "#C8D0DA"),
]

QUICK_ACTIONS = [
    ("Heure", "Quelle heure est-il ?"),
    ("Météo", "Quel temps fait-il ?"),
    ("Mails", "Lis mes derniers mails"),
    ("Gmail", "Connecte Gmail"),
    ("Spotify", "Ouvre Spotify"),
    ("Chrome", "Ouvre Chrome"),
    ("Vol 50", "Mets le volume à 50 %"),
    ("Verrouiller", "Verrouille l'écran"),
]

MODULES = [
    ("IA", "online"),
    ("Mobile", "online"),
    ("Voix", "online"),
    ("Micro", "micro"),
    ("Gmail", "online"),
    ("Système", "online"),
]

_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def normaliser_hex(valeur: str | None, defaut: str = "#4EC9D4") -> str:
    raw = (valeur or "").strip()
    if not raw:
        return defaut.upper() if defaut.startswith("#") else f"#{defaut.upper()}"
    if not raw.startswith("#"):
        raw = f"#{raw}"
    if not _HEX_RE.match(raw):
        return defaut.upper() if defaut.startswith("#") else f"#{defaut.upper()}"
    return raw.upper()


def est_hex_valide(valeur: str | None) -> bool:
    raw = (valeur or "").strip()
    if not raw:
        return False
    if not raw.startswith("#"):
        raw = f"#{raw}"
    return bool(_HEX_RE.match(raw))


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = normaliser_hex(h)
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02X}{max(0, min(255, g)):02X}{max(0, min(255, b)):02X}"


def _mix(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


def _scale(c: str, factor: float) -> str:
    r, g, b = _hex_to_rgb(c)
    return _rgb_to_hex(int(r * factor), int(g * factor), int(b * factor))


def appliquer_accent(hex_color: str, intensite: float = 1.0) -> str:
    """Met à jour ACCENT et dérivés au runtime. Retourne l'hex normalisé."""
    global ACCENT, ACCENT_SOFT, ACCENT_DIM, ACCENT_GLOW, ACCENT_HOT
    global ACCENT_INTENSITY, _ACCENT_BASE, GLASS_BORDER_HOT

    base = normaliser_hex(hex_color)
    try:
        intensite = float(intensite)
    except (TypeError, ValueError):
        intensite = 1.0
    intensite = max(0.55, min(1.0, intensite))
    _ACCENT_BASE = base
    ACCENT_INTENSITY = intensite

    # Mix vers graphite si intensité basse
    accent = _mix("#6A7380", base, intensite)
    ACCENT = accent
    ACCENT_SOFT = _mix(accent, "#E8F6F8", 0.35)
    ACCENT_HOT = _mix(accent, "#FFFFFF", 0.45)
    ACCENT_DIM = _mix(BG_PANEL, accent, 0.38)
    ACCENT_GLOW = _mix(BG_DEEP, accent, 0.22)
    GLASS_BORDER_HOT = _mix(LINE, accent, 0.55)
    return accent


def charger_accent_profil(profil: dict | None = None) -> str:
    """Charge couleur_ia / accent_hex (+ intensité) depuis le profil."""
    if profil is None:
        try:
            from config import lire_profil
            profil = lire_profil()
        except Exception:
            profil = {}
    hex_c = profil.get("couleur_ia") or profil.get("accent_hex") or _ACCENT_BASE
    try:
        intensite = float(profil.get("accent_intensite") or 1.0)
    except (TypeError, ValueError):
        intensite = 1.0
    return appliquer_accent(hex_c, intensite)


def accent_rgba(alpha: float = 0.35) -> str:
    """Pour canvas / effets — retourne hex (alpha ignoré hors Tk)."""
    return ACCENT


# Charger accent profil au import (si .env déjà là)
try:
    charger_accent_profil()
except Exception:
    appliquer_accent(_ACCENT_BASE, 1.0)
