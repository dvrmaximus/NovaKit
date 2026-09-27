"""Conseiller IA Performance — heuristique locale + tip Gemini optionnel (non bloquant)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from core.gaming_estimate import HardwareProfile, detect_hardware, estimer_presets
from core.perf_monitor import snapshot


@dataclass
class AdvicePack:
    score: int = 50
    profil: str = "Equilibre"
    jeu: str = ""
    resolution: str = "1080p"
    fps_cible: int = 60
    qualite: str = "medium"
    activer_mode_perf: bool = True
    a_fermer: list[str] = field(default_factory=list)
    cartes: list[str] = field(default_factory=list)
    tip_ia: str = ""
    preset_patch: dict[str, Any] = field(default_factory=dict)


_GAME_HINTS: list[tuple[str, str]] = [
    ("valorant", "Jeux competitifs (Valorant-like)"),
    ("cs2", "Jeux competitifs (Valorant-like)"),
    ("csgo", "Jeux competitifs (Valorant-like)"),
    ("overwatch", "Jeux competitifs (Valorant-like)"),
    ("fortnite", "Battle royale (Fortnite-like)"),
    ("warzone", "Battle royale (Fortnite-like)"),
    ("apex", "Battle royale (Fortnite-like)"),
    ("gta", "Open world (GTA-like)"),
    ("red dead", "Open world (GTA-like)"),
    ("cyberpunk", "AAA raytracing (Cyberpunk-like)"),
    ("alan wake", "AAA raytracing (Cyberpunk-like)"),
    ("control", "AAA raytracing (Cyberpunk-like)"),
]


def machine_score(hw: HardwareProfile | None = None) -> int:
    hw = hw or detect_hardware()
    score = 20 + hw.gpu_tier * 12
    ram = hw.ram_gb or 8.0
    if ram >= 32:
        score += 15
    elif ram >= 16:
        score += 10
    elif ram >= 8:
        score += 4
    else:
        score -= 8
    cores = hw.cpu_cores or 4
    if cores >= 16:
        score += 10
    elif cores >= 12:
        score += 7
    elif cores >= 8:
        score += 4
    return int(max(5, min(99, score)))


def profil_label(score: int) -> str:
    if score >= 85:
        return "Flagship"
    if score >= 70:
        return "Hautes perfs"
    if score >= 55:
        return "Equilibre"
    if score >= 40:
        return "Competitif leger"
    return "Eco / entry"


def _match_scenario(jeu: str) -> str | None:
    j = (jeu or "").strip().lower()
    if not j or j in ("jeu actuel", "actuel", "auto"):
        return None
    for key, scenario in _GAME_HINTS:
        if key in j:
            return scenario
    return None


def build_advice(
    jeu: str = "",
    *,
    aggressiveness: float = 0.5,
    hw: HardwareProfile | None = None,
) -> AdvicePack:
    hw = hw or detect_hardware()
    score = machine_score(hw)
    profil = profil_label(score)
    est = estimer_presets(hw, aggressiveness=aggressiveness)
    scenario = _match_scenario(jeu)
    chosen = None
    if scenario:
        for e in est:
            if e.scenario == scenario:
                chosen = e
                break
    if chosen is None and est:
        # Defaut : competitif si score moyen+, sinon open world prudent
        chosen = est[0] if score >= 55 else est[2] if len(est) > 2 else est[0]

    snap = snapshot()
    a_fermer: list[str] = []
    if snap.ram_percent >= 75:
        a_fermer.append("Onglets navigateur lourds (RAM elevee)")
    if snap.cpu_percent >= 60:
        a_fermer.append("Apps de fond CPU (Discord overlay, launchers)")
    a_fermer.append("Overlays inutiles (GeForce Experience / Discord)")

    activer = score < 80 or snap.ram_percent >= 70 or (hw.gpu_tier or 2) <= 3

    cartes = [
        f"Score machine : {score}/100 — profil « {profil} »",
        f"CPU : {hw.cpu_name}",
        f"GPU : {hw.gpu_name}" + (f" ({hw.gpu_vram_gb:.0f} Go)" if hw.gpu_vram_gb else ""),
        f"RAM : {hw.ram_gb:.0f} Go",
    ]
    if chosen:
        cartes.append(
            f"Pour « {jeu or chosen.scenario} » → {chosen.resolution} · "
            f"{chosen.qualite} · ~{chosen.fps_cible} FPS"
        )
        cartes.append(chosen.resume)
    if activer:
        cartes.append("Conseil : activer Mode Performance (plan OS + anti-lag Astat).")
    else:
        cartes.append("Machine confortable — Mode Performance optionnel.")

    patch = {
        "gaming": {
            "resolution_preset": (chosen.resolution.lower() if chosen else "auto"),
            "quality_preset": _map_quality(chosen.qualite if chosen else "medium"),
        },
        "perf": {
            "mode_performance": bool(activer),
            "advisor_last_game": jeu or "",
            "advisor_last_score": score,
            "advisor_last_profil": profil,
        },
    }
    # Normaliser resolution presets connus
    res = patch["gaming"]["resolution_preset"]
    if res not in ("auto", "1080p", "1440p", "4k"):
        if "4" in res.lower():
            res = "4k"
        elif "1440" in res or "2k" in res:
            res = "1440p"
        else:
            res = "1080p"
        patch["gaming"]["resolution_preset"] = res

    return AdvicePack(
        score=score,
        profil=profil,
        jeu=jeu or (chosen.scenario if chosen else ""),
        resolution=patch["gaming"]["resolution_preset"],
        fps_cible=int(chosen.fps_cible) if chosen else 60,
        qualite=patch["gaming"]["quality_preset"],
        activer_mode_perf=activer,
        a_fermer=a_fermer,
        cartes=cartes,
        tip_ia="",
        preset_patch=patch,
    )


def _map_quality(q: str) -> str:
    q = (q or "medium").lower()
    if q in ("auto", "low", "medium", "high", "ultra"):
        return q
    if q in ("epic", "very high", "ultra"):
        return "ultra"
    if "high" in q:
        return "high"
    if "low" in q:
        return "low"
    return "medium"


def apply_advice(pack: AdvicePack, *, enable_boost: bool = True) -> str:
    """Applique presets + Mode Performance. Retourne message FR."""
    from core import mode_settings
    from core import perf_boost

    mode_settings.save(pack.preset_patch)
    msgs = [f"Presets enregistres : {pack.resolution} / {pack.qualite}."]
    if enable_boost and pack.activer_mode_perf:
        st = perf_boost.enable(lower_bg=False, enable_game_mode=True)
        msgs.append("Mode Performance active.")
        msgs.extend(st.get("lines") or [])
    elif enable_boost and not pack.activer_mode_perf:
        msgs.append("Mode Performance laisse inactif (machine deja confortable).")
    return " ".join(msgs)


def fetch_gemini_tip_async(
    pack: AdvicePack,
    on_done: Callable[[str], None] | None = None,
) -> None:
    """Appel Gemini court en thread — ne bloque pas l'UI."""

    def _run():
        tip = ""
        try:
            tip = _gemini_tip(pack)
        except Exception:
            tip = ""
        if on_done:
            try:
                on_done(tip)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True, name="perf-advisor-gemini").start()


def _gemini_tip(pack: AdvicePack) -> str:
    """Une phrase FR max — sans outils."""
    try:
        from google import genai
        from google.genai import types
        from config import API_KEY, API_KEYS, MODELE_GEMINI
    except Exception:
        return ""

    cles = list(API_KEYS) if API_KEYS else ([API_KEY] if API_KEY else [])
    if not cles:
        return ""

    prompt = (
        "Tu es un conseiller PC gaming francais. Une seule phrase courte (max 25 mots). "
        "Pas de markdown. Conseille un reglage concret. "
        f"Score {pack.score}, profil {pack.profil}, jeu {pack.jeu or 'general'}, "
        f"vise {pack.resolution} {pack.qualite} ~{pack.fps_cible} FPS."
    )
    try:
        client = genai.Client(api_key=cles[0])
        resp = client.models.generate_content(
            model=MODELE_GEMINI or "gemini-2.0-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=80),
        )
        text = (getattr(resp, "text", None) or "").strip()
        return text[:220]
    except Exception:
        return ""
