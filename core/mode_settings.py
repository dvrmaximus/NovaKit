"""Reglages persistants des modes Performance / Gaming (data/mode_settings.json)."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from typing import Any

from config import DATA_DIR

SETTINGS_FILE = DATA_DIR / "mode_settings.json"
_lock = threading.Lock()
_cache: dict[str, Any] | None = None

DEFAULTS: dict[str, Any] = {
    "perf": {
        "refresh_hz": 1.5,
        "show_cpu": True,
        "show_ram": True,
        "show_gpu": True,
        "show_disk": True,
        "show_net": True,
        "show_temps": True,
        "show_fps": True,
        "alert_cpu": 90,
        "alert_ram": 90,
        "alert_gpu": 95,
        "history_points": 60,
        "mode_performance": False,
        "boost_game_mode": True,
        "boost_lower_bg": False,
        "boost_apps": ["discord", "chrome"],
        "advisor_last_game": "",
        "advisor_last_score": 0,
        "advisor_last_profil": "",
    },
    "gaming": {
        "resolution_preset": "auto",
        "quality_preset": "auto",
        "aggressiveness": 0.5,
        "hud_fps_overlay": True,
        "bench_duration_s": 2.5,
    },
    "global": {
        "open_window_on_mode": False,  # defaut : tout dans Astat (onglets)
        "always_on_top": False,
        "opacity": 0.96,
    },
}


def _deep_merge(base: dict, patch: dict) -> dict:
    out = deepcopy(base)
    for k, v in (patch or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load() -> dict[str, Any]:
    global _cache
    with _lock:
        if _cache is not None:
            return deepcopy(_cache)
        data = deepcopy(DEFAULTS)
        try:
            if SETTINGS_FILE.exists():
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = _deep_merge(DEFAULTS, raw)
        except Exception:
            data = deepcopy(DEFAULTS)
        _cache = data
        return deepcopy(data)


def save(patch: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fusionne un patch partiel et ecrit le fichier. Retourne l'etat final."""
    global _cache
    with _lock:
        current = deepcopy(_cache) if _cache is not None else deepcopy(DEFAULTS)
        if _cache is None and SETTINGS_FILE.exists():
            try:
                raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    current = _deep_merge(DEFAULTS, raw)
            except Exception:
                pass
        if patch:
            current = _deep_merge(current, patch)
        current = _sanitize(current)
        try:
            DATA_DIR.mkdir(exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(current, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass
        _cache = current
        return deepcopy(current)


def get_section(name: str) -> dict[str, Any]:
    return load().get(name) or deepcopy(DEFAULTS.get(name, {}))


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    out = _deep_merge(DEFAULTS, data)
    p = out["perf"]
    try:
        p["refresh_hz"] = max(0.5, min(4.0, float(p.get("refresh_hz", 1.5))))
    except (TypeError, ValueError):
        p["refresh_hz"] = 1.5
    for key in ("alert_cpu", "alert_ram", "alert_gpu"):
        try:
            p[key] = int(max(50, min(100, float(p.get(key, 90)))))
        except (TypeError, ValueError):
            p[key] = 90
    try:
        p["history_points"] = int(max(20, min(120, float(p.get("history_points", 60)))))
    except (TypeError, ValueError):
        p["history_points"] = 60
    for key in ("show_cpu", "show_ram", "show_gpu", "show_disk", "show_net", "show_temps", "show_fps"):
        p[key] = bool(p.get(key, True))
    p["mode_performance"] = bool(p.get("mode_performance", False))
    p["boost_game_mode"] = bool(p.get("boost_game_mode", True))
    p["boost_lower_bg"] = bool(p.get("boost_lower_bg", False))
    apps = p.get("boost_apps")
    if not isinstance(apps, list):
        apps = ["discord", "chrome"]
    p["boost_apps"] = [str(a) for a in apps][:24]
    p["advisor_last_game"] = str(p.get("advisor_last_game") or "")
    try:
        p["advisor_last_score"] = int(max(0, min(100, float(p.get("advisor_last_score") or 0))))
    except (TypeError, ValueError):
        p["advisor_last_score"] = 0
    p["advisor_last_profil"] = str(p.get("advisor_last_profil") or "")

    g = out["gaming"]
    res = str(g.get("resolution_preset") or "auto").lower()
    if res not in ("auto", "1080p", "1440p", "4k"):
        res = "auto"
    g["resolution_preset"] = res
    qual = str(g.get("quality_preset") or "auto").lower()
    if qual not in ("auto", "low", "medium", "high", "ultra"):
        qual = "auto"
    g["quality_preset"] = qual
    try:
        g["aggressiveness"] = max(0.0, min(1.0, float(g.get("aggressiveness", 0.5))))
    except (TypeError, ValueError):
        g["aggressiveness"] = 0.5
    g["hud_fps_overlay"] = bool(g.get("hud_fps_overlay", True))
    try:
        g["bench_duration_s"] = max(1.0, min(5.0, float(g.get("bench_duration_s", 2.5))))
    except (TypeError, ValueError):
        g["bench_duration_s"] = 2.5

    gl = out["global"]
    gl["open_window_on_mode"] = bool(gl.get("open_window_on_mode", False))
    gl["always_on_top"] = bool(gl.get("always_on_top", False))
    try:
        gl["opacity"] = max(0.55, min(1.0, float(gl.get("opacity", 0.96))))
    except (TypeError, ValueError):
        gl["opacity"] = 0.96
    return out
