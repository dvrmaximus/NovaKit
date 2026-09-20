"""Entraînement du prénom / mot de réveil via aliases STT (sans modèle ML)."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from config import DATA_DIR, NOM_IA, MOT_MAGIQUE

WAKE_FILE = DATA_DIR / "wake_training.json"

MIN_SAMPLES = 3
TARGET_SAMPLES = 4
MAX_TRANSCRIPT_CHARS = 40
MAX_WORDS = 5
RATIO_DEFAUT = 0.72


def _norm(texte: str) -> str:
    """Minuscules, sans accents, ponctuation → espaces, espaces compressés."""
    s = unicodedata.normalize("NFKD", (texte or "").strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"_+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def variantes_auto(nom: str) -> list[str]:
    """Variantes phonétiques / STT courantes à partir du nom officiel."""
    n = _norm(nom)
    if not n:
        return []
    out: set[str] = {n, n.replace(" ", ""), n.replace("-", " ")}
    compact = n.replace(" ", "")
    if compact:
        out.add(compact)
    # Coupures au milieu (ex. astat → as tat / a stat)
    if " " not in compact and 3 <= len(compact) <= 10:
        mid = len(compact) // 2
        for cut in {mid, mid - 1, mid + 1, 2, 3}:
            if 1 <= cut < len(compact):
                out.add(f"{compact[:cut]} {compact[cut:]}")
    # Préfixes souvent collés par Google STT FR
    for pref in ("a ", "ah ", "à ", "hey ", "hé ", "oi ", "oh ", "euh "):
        out.add(pref + n)
        if compact != n:
            out.add(pref + compact)
    # Homophones / confusions fréquentes pour quelques prénoms connus
    connus = {
        "astat": ["a state", "ah stat", "as tat", "astate", "has that", "a start", "as that"],
        "nova": ["nova", "nova", "no va", "noah"],
        "aria": ["aria", "haria", "arya", "area"],
        "atlas": ["atlas", "at lass", "at last"],
        "echo": ["echo", "écho", "eko"],
        "jarvis": ["jarvis", "jar vis", "javis"],
        "nyx": ["nyx", "nix", "nicks"],
    }
    for k, vals in connus.items():
        if compact == k or n == k:
            out.update(_norm(v) for v in vals)
    return sorted({v for v in out if v and len(v) >= 2})


def _defaut() -> dict:
    return {
        "version": 1,
        "nom_ia": "",
        "min_samples": MIN_SAMPLES,
        "target_samples": TARGET_SAMPLES,
        "ratio_min": RATIO_DEFAUT,
        "samples": [],
        "aliases": [],
        "enabled": False,
        "updated_at": "",
    }


def charger() -> dict:
    data = _defaut()
    if not WAKE_FILE.exists():
        return data
    try:
        raw = json.loads(WAKE_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update(raw)
    except Exception:
        pass
    data["samples"] = list(data.get("samples") or [])
    data["aliases"] = list(data.get("aliases") or [])
    try:
        data["ratio_min"] = float(data.get("ratio_min") or RATIO_DEFAUT)
    except (TypeError, ValueError):
        data["ratio_min"] = RATIO_DEFAUT
    try:
        data["min_samples"] = max(2, int(data.get("min_samples") or MIN_SAMPLES))
    except (TypeError, ValueError):
        data["min_samples"] = MIN_SAMPLES
    data["enabled"] = bool(data.get("enabled")) and len(data["aliases"]) >= data["min_samples"]
    return data


def sauvegarder(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "version": 1,
        "nom_ia": data.get("nom_ia") or "",
        "min_samples": int(data.get("min_samples") or MIN_SAMPLES),
        "target_samples": int(data.get("target_samples") or TARGET_SAMPLES),
        "ratio_min": float(data.get("ratio_min") or RATIO_DEFAUT),
        "samples": list(data.get("samples") or []),
        "aliases": sorted({_norm(a) for a in (data.get("aliases") or []) if _norm(a)}),
        "enabled": bool(data.get("enabled")),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    payload["enabled"] = len(payload["aliases"]) >= payload["min_samples"]
    WAKE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def reinitialiser() -> dict:
    data = _defaut()
    sauvegarder(data)
    return data


def statut_texte(nom_ia: str | None = None) -> str:
    data = charger()
    nom = (nom_ia or data.get("nom_ia") or NOM_IA or "?").strip()
    n = len(data.get("aliases") or [])
    mini = int(data.get("min_samples") or MIN_SAMPLES)
    if data.get("enabled") and n >= mini:
        return f"Prénom entraîné ({n} variantes) — {nom}"
    if n:
        return f"Entraînement incomplet : {n}/{mini} — {nom}"
    return f"Pas encore entraîné — dis « {nom} » plusieurs fois"


def valider_echantillon(transcript: str) -> tuple[bool, str, str]:
    """Retourne (ok, message_erreur, forme_normalisée)."""
    brut = (transcript or "").strip()
    if not brut:
        return False, "Je n'ai rien entendu.", ""
    if len(brut) > MAX_TRANSCRIPT_CHARS:
        return False, "Trop long — dis seulement mon prénom.", ""
    mots = brut.split()
    if len(mots) > MAX_WORDS:
        return False, "Une seule expression courte, s'il te plaît.", ""
    n = _norm(brut)
    if len(n) < 2:
        return False, "Trop court.", ""
    return True, "", n


def ajouter_echantillon(transcript: str, nom_ia: str | None = None) -> dict:
    ok, err, normalise = valider_echantillon(transcript)
    if not ok:
        raise ValueError(err)
    data = charger()
    nom = (nom_ia or NOM_IA or "").strip()
    data["nom_ia"] = nom
    samples = list(data.get("samples") or [])
    samples.append({
        "transcript": transcript.strip(),
        "normalized": normalise,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    data["samples"] = samples[-40:]  # historique borné
    aliases = {_norm(a) for a in (data.get("aliases") or []) if _norm(a)}
    aliases.add(normalise)
    # aussi le transcript brut normalisé mot à mot
    aliases.add(_norm(transcript))
    data["aliases"] = sorted(aliases)
    mini = int(data.get("min_samples") or MIN_SAMPLES)
    data["enabled"] = len(data["aliases"]) >= mini
    sauvegarder(data)
    return data


def aliases_actifs(noms_officiels: Iterable[str] | None = None) -> list[str]:
    """Liste des formes à matcher : officiels + auto + entraînés (si activés)."""
    data = charger()
    out: set[str] = set()
    officiels = list(noms_officiels or [])
    if not officiels:
        officiels = [MOT_MAGIQUE or "", NOM_IA or ""]
    for m in officiels:
        m = _norm(str(m))
        if m:
            out.add(m)
            out.update(variantes_auto(m))
    if data.get("enabled"):
        for a in data.get("aliases") or []:
            n = _norm(a)
            if n:
                out.add(n)
    return sorted(out, key=len, reverse=True)


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def trouver_reveil(
    texte: str,
    noms_officiels: Iterable[str] | None = None,
    ratio_min: float | None = None,
) -> tuple[int, int] | None:
    """
    Cherche le prénom / alias dans le texte entendu.
    Retourne (index, longueur) dans le texte original (minuscules), ou None.
    """
    brut = (texte or "").strip()
    if not brut:
        return None
    bas = brut.lower()
    norm = _norm(brut)
    if not norm:
        return None

    data = charger()
    try:
        seuil = float(ratio_min if ratio_min is not None else data.get("ratio_min") or RATIO_DEFAUT)
    except (TypeError, ValueError):
        seuil = RATIO_DEFAUT
    seuil = max(0.55, min(0.95, seuil))

    aliases = aliases_actifs(noms_officiels)

    # 1) Correspondance exacte (limites de mot) sur le texte brut
    meilleur: tuple[int, int] | None = None
    for alias in aliases:
        if not alias:
            continue
        # alias peut contenir des espaces → pattern souple
        pat = r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"\s+") + r"(?!\w)"
        for match in re.finditer(pat, bas, flags=re.IGNORECASE):
            pos = (match.start(), match.end() - match.start())
            if meilleur is None or pos[0] < meilleur[0] or (
                pos[0] == meilleur[0] and pos[1] > meilleur[1]
            ):
                meilleur = pos
            break
        if meilleur is None and alias in bas:
            meilleur = (bas.index(alias), len(alias))
    if meilleur is not None:
        return meilleur

    # 2) Exact sur forme normalisée → remonter une fenêtre dans le brut
    for alias in aliases:
        if alias and alias in norm:
            # si toute la phrase est l'alias (ou presque)
            if _ratio(norm, alias) >= 0.9 or norm == alias:
                return (0, len(brut))
            # sinon : fuzzy fenêtre ci-dessous
            break

    # 3) Similarité sur fenêtres de 1–3 mots
    mots = bas.split()
    if not mots:
        return None
    best_score = 0.0
    best_span: tuple[int, int] | None = None
    for n_mots in range(1, min(4, len(mots) + 1)):
        for i in range(len(mots) - n_mots + 1):
            fenetre = " ".join(mots[i : i + n_mots])
            fen_n = _norm(fenetre)
            if len(fen_n) < 2:
                continue
            for alias in aliases:
                score = _ratio(fen_n, _norm(alias))
                # bonus si alias contenu
                if fen_n == _norm(alias) or fen_n in _norm(alias) or _norm(alias) in fen_n:
                    score = max(score, 0.92)
                if score >= seuil and score > best_score:
                    best_score = score
                    # localiser dans bas
                    idx = bas.find(fenetre)
                    if idx < 0:
                        idx = 0
                        length = len(brut)
                    else:
                        length = len(fenetre)
                    best_span = (idx, length)
    return best_span


def est_entraine() -> bool:
    data = charger()
    return bool(data.get("enabled")) and len(data.get("aliases") or []) >= int(
        data.get("min_samples") or MIN_SAMPLES
    )
