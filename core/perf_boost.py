"""Mode Performance — optimisations OS sures (pas d'injection jeux / Anti-Lag driver).

Actions :
- plan d'alimentation Haute performance / Ultimate (restauration au desabonnement)
- Game Mode Windows via registre (best-effort)
- baisse optionnelle de priorite de processus non critiques (liste curatee)
- signal pour reduire les timers / FPS idle de NovaKit

Ne tue jamais de processus Windows critiques.
"""

from __future__ import annotations

import subprocess
import threading
from copy import deepcopy
from typing import Any

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_OK = False

from core import mode_settings

_lock = threading.Lock()
_state: dict[str, Any] = {
    "active": False,
    "prev_power_scheme": None,
    "game_mode_ok": None,
    "game_mode_msg": "",
    "lowered_pids": [],  # [{"pid", "name", "prev_nice"}]
    "status_lines": [],
}

# Processus optionnels (jamais systeme) — priorite basse seulement
SAFE_BG_APPS: list[tuple[str, str]] = [
    ("discord", "Discord (overlay / idle)"),
    ("chrome", "Google Chrome"),
    ("msedge", "Microsoft Edge"),
    ("firefox", "Firefox"),
    ("spotify", "Spotify"),
    ("steamwebhelper", "Steam WebHelper"),
    ("slack", "Slack"),
    ("teams", "Microsoft Teams"),
    ("onedrive", "OneDrive"),
]

# Ne jamais toucher
_PROTECTED = frozenset({
    "system", "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
    "lsass.exe", "svchost.exe", "winlogon.exe", "explorer.exe",
    "dwm.exe", "fontdrvhost.exe", "sihost.exe", "taskhostw.exe",
    "python.exe", "pythonw.exe", "astat", "novakit",
})


def is_active() -> bool:
    with _lock:
        return bool(_state["active"])


def status_summary() -> dict[str, Any]:
    with _lock:
        return {
            "active": bool(_state["active"]),
            "lines": list(_state["status_lines"]),
            "game_mode_ok": _state["game_mode_ok"],
            "game_mode_msg": _state["game_mode_msg"] or "",
            "lowered": len(_state["lowered_pids"]),
        }


def enable(
    *,
    lower_bg: bool = False,
    selected_apps: list[str] | None = None,
    enable_game_mode: bool = True,
) -> dict[str, Any]:
    """Active le Mode Performance. Idempotent si deja actif (re-applique options)."""
    lines: list[str] = []
    with _lock:
        if _state["active"]:
            # deja actif : eventuellement re-baisser priorites
            pass
        else:
            _state["prev_power_scheme"] = _get_active_power_scheme()
            ok_power, msg_power = _set_high_performance()
            lines.append(msg_power)
            if enable_game_mode:
                gm_ok, gm_msg = _enable_game_mode()
                _state["game_mode_ok"] = gm_ok
                _state["game_mode_msg"] = gm_msg
                lines.append(gm_msg)
            _state["active"] = True

        if lower_bg:
            apps = selected_apps if selected_apps is not None else [
                a for a, _ in SAFE_BG_APPS
            ]
            n = _lower_background_priority(apps)
            lines.append(
                f"Priorite baissee pour {n} processus (non critiques)."
                if n else "Aucun processus cible trouve a baisser."
            )
        else:
            lines.append("Priorites processus : inchangees (conseils manuels).")

        lines.append(
            "Anti-lag Astat = charge fond reduite + focus avant-plan "
            "(pas de controle driver AMD Anti-Lag)."
        )
        _state["status_lines"] = lines

    mode_settings.save({
        "perf": {
            "mode_performance": True,
            "boost_lower_bg": bool(lower_bg),
            "boost_apps": list(selected_apps or []),
            "boost_game_mode": bool(enable_game_mode),
        },
    })
    return status_summary()


def disable() -> dict[str, Any]:
    """Desactive et restaure plan d'alimentation + priorites."""
    lines: list[str] = []
    with _lock:
        if not _state["active"] and not _state["lowered_pids"]:
            mode_settings.save({"perf": {"mode_performance": False}})
            return status_summary()

        prev = _state.get("prev_power_scheme")
        if prev:
            ok, msg = _set_power_scheme(prev)
            lines.append(msg if ok else f"Restauration plan : {msg}")
        else:
            lines.append("Plan d'alimentation : aucun precedent a restaurer.")

        restored = _restore_priorities()
        if restored:
            lines.append(f"Priorites restaurees ({restored}).")

        _state["active"] = False
        _state["prev_power_scheme"] = None
        _state["status_lines"] = lines or ["Mode Performance desactive."]
        _state["game_mode_ok"] = None

    mode_settings.save({"perf": {"mode_performance": False}})
    return status_summary()


def apply_from_settings() -> None:
    """Au demarrage : reactive si preference persistee."""
    cfg = mode_settings.get_section("perf")
    if not cfg.get("mode_performance"):
        return
    enable(
        lower_bg=bool(cfg.get("boost_lower_bg", False)),
        selected_apps=list(cfg.get("boost_apps") or []),
        enable_game_mode=bool(cfg.get("boost_game_mode", True)),
    )


def tips_fr() -> list[str]:
    return [
        "Ferme les onglets Chrome inutiles avant une session longue.",
        "Desactive l'overlay Discord si tu cherches chaque ms (Parametres Discord).",
        "Mode Jeu Windows : deja tente via registre si autorise.",
        "Timer resolution OS : laisse Windows gerer — pas de tweak agressif ici.",
        "Anti-lag Astat = moins de fond + plan perf, pas l'Anti-Lag AMD driver.",
    ]


def _run(cmd: list[str], timeout: float = 4.0) -> tuple[int, str]:
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags,
        )
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return int(p.returncode), out
    except Exception as exc:
        return 1, str(exc)


def _get_active_power_scheme() -> str | None:
    code, out = _run(["powercfg", "/getactivescheme"])
    if code != 0:
        return None
    # GUID: xxxxxxxx-....
    import re
    m = re.search(
        r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        out,
    )
    return m.group(1) if m else None


def _list_schemes() -> list[tuple[str, str]]:
    code, out = _run(["powercfg", "/list"])
    if code != 0:
        return []
    import re
    found = []
    for line in out.splitlines():
        m = re.search(
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
            r".*\(([^)]+)\)",
            line,
        )
        if m:
            found.append((m.group(1), m.group(2)))
    return found


def _set_power_scheme(guid: str) -> tuple[bool, str]:
    code, out = _run(["powercfg", "/setactive", guid])
    if code == 0:
        return True, f"Plan d'alimentation active ({guid[:8]}…)."
    return False, out or "Echec powercfg /setactive"


def _set_high_performance() -> tuple[bool, str]:
    schemes = _list_schemes()
    # Prefer Ultimate Performance, puis High performance / Performances elevees
    prefer = (
        "ultimate",
        "performances ultimes",
        "high performance",
        "performances elevees",
        "hautes performances",
        "performance",
    )
    chosen = None
    for guid, name in schemes:
        low = name.lower()
        for p in prefer:
            if p in low:
                chosen = (guid, name)
                break
        if chosen and ("ultimate" in chosen[1].lower() or "ultime" in chosen[1].lower()):
            break
    if not chosen:
        # GUID classique High Performance
        chosen = ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "Hautes performances")
    ok, msg = _set_power_scheme(chosen[0])
    if ok:
        return True, f"Plan « {chosen[1]} » active."
    return False, f"Plan perf indisponible : {msg}"


def _enable_game_mode() -> tuple[bool, str]:
    """Best-effort : cle GameDVR / GameMode AllowAutoGameMode."""
    ps = (
        "$p='HKCU:\\Software\\Microsoft\\GameBar'; "
        "if(-not (Test-Path $p)){New-Item -Path $p -Force|Out-Null}; "
        "New-ItemProperty -Path $p -Name AutoGameModeEnabled -Value 1 -PropertyType DWord -Force|Out-Null; "
        "$p2='HKCU:\\Software\\Microsoft\\GameBar'; "
        "New-ItemProperty -Path $p2 -Name AllowAutoGameMode -Value 1 -PropertyType DWord -Force -ErrorAction SilentlyContinue|Out-Null; "
        "Write-Output 'ok'"
    )
    code, out = _run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        timeout=6.0,
    )
    if code == 0 and "ok" in (out or "").lower():
        return True, "Mode Jeu Windows : active (registre, best-effort)."
    return False, f"Mode Jeu Windows : echec ou refuse ({out or 'n/d'})."


def _lower_background_priority(app_keys: list[str]) -> int:
    if not PSUTIL_OK:
        return 0
    keys = {k.lower() for k in app_keys}
    count = 0
    with _lock:
        already = {e["pid"] for e in _state["lowered_pids"]}
    try:
        for proc in psutil.process_iter(["pid", "name", "nice"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if not name or name in _PROTECTED:
                    continue
                base = name.replace(".exe", "")
                if base in _PROTECTED:
                    continue
                match = any(k in base or base.startswith(k) for k in keys)
                if not match:
                    continue
                pid = int(proc.info["pid"])
                if pid in already:
                    continue
                prev = proc.nice()
                # Windows : BELOW_NORMAL_PRIORITY_CLASS ≈ nice psutil
                try:
                    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                except AttributeError:
                    proc.nice(10)  # unix-ish fallback
                with _lock:
                    _state["lowered_pids"].append({
                        "pid": pid, "name": name, "prev_nice": prev,
                    })
                count += 1
            except (psutil.Error, OSError, ValueError):
                continue
    except Exception:
        pass
    return count


def _restore_priorities() -> int:
    if not PSUTIL_OK:
        with _lock:
            _state["lowered_pids"] = []
        return 0
    n = 0
    with _lock:
        entries = list(_state["lowered_pids"])
        _state["lowered_pids"] = []
    for e in entries:
        try:
            p = psutil.Process(int(e["pid"]))
            prev = e.get("prev_nice")
            if prev is not None:
                p.nice(prev)
            else:
                try:
                    p.nice(psutil.NORMAL_PRIORITY_CLASS)
                except AttributeError:
                    p.nice(0)
            n += 1
        except (psutil.Error, OSError, ValueError):
            continue
    return n


def snapshot_state() -> dict[str, Any]:
    with _lock:
        return deepcopy(_state)
