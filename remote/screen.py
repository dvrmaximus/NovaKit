"""Capture d'écran haute fréquence (cible ~30 FPS) multi-écrans."""

from __future__ import annotations

import threading
import time
from io import BytesIO
from typing import Any, Optional

from tools.pc_control import SCREENSHOT_DIR

_lock = threading.Lock()
_latest_jpeg: Optional[bytes] = None
_clients = 0
_thread: Optional[threading.Thread] = None
_running = False

FPS_CIBLE = 30

_settings_lock = threading.Lock()
_largeur = 960
_qualite = 40
_moniteur = 1  # index mss (1 = premier écran, 2 = second, …)


def regler_qualite(mode: str = "eco"):
    global _largeur, _qualite
    with _settings_lock:
        if mode == "hq":
            _largeur, _qualite = 1280, 55
        else:
            _largeur, _qualite = 960, 40


def _params():
    with _settings_lock:
        return _largeur, _qualite, _moniteur


def lister_ecrans() -> list[dict[str, Any]]:
    """Liste les moniteurs physiques (sans le moniteur 0 = bureau virtuel)."""
    try:
        import mss
        with mss.mss() as sct:
            ecrans = []
            for i, mon in enumerate(sct.monitors[1:], start=1):
                ecrans.append({
                    "index": i,
                    "width": mon["width"],
                    "height": mon["height"],
                    "left": mon["left"],
                    "top": mon["top"],
                    "label": f"Écran {i} ({mon['width']}×{mon['height']})",
                })
            return ecrans
    except Exception:
        return [{"index": 1, "width": 1920, "height": 1080, "left": 0, "top": 0, "label": "Écran 1"}]


def choisir_ecran(index: int) -> dict[str, Any]:
    """Sélectionne l'écran à streamer (1, 2, …)."""
    global _moniteur
    ecrans = lister_ecrans()
    if not ecrans:
        raise ValueError("Aucun écran détecté")
    indices = {e["index"] for e in ecrans}
    if index not in indices:
        raise ValueError(f"Écran {index} introuvable. Dispo : {sorted(indices)}")
    with _settings_lock:
        _moniteur = index
    return next(e for e in ecrans if e["index"] == index)


def ecran_actuel() -> dict[str, Any]:
    with _settings_lock:
        idx = _moniteur
    ecrans = lister_ecrans()
    for e in ecrans:
        if e["index"] == idx:
            return e
    return ecrans[0] if ecrans else {"index": 1, "width": 1920, "height": 1080, "left": 0, "top": 0}


def geometrie_ecran_actif() -> dict[str, int]:
    """Géométrie absolue de l'écran sélectionné (pour les clics)."""
    info = ecran_actuel()
    return {
        "left": int(info.get("left", 0)),
        "top": int(info.get("top", 0)),
        "width": int(info.get("width", 1920)),
        "height": int(info.get("height", 1080)),
    }


def _encoder_mss(largeur_max: int, qualite: int, moniteur: int) -> bytes:
    import mss
    from PIL import Image

    with mss.mss() as sct:
        mons = sct.monitors
        idx = moniteur if 0 < moniteur < len(mons) else 1
        mon = mons[idx]
        raw = sct.grab(mon)
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

    if img.width > largeur_max:
        ratio = largeur_max / img.width
        img = img.resize(
            (largeur_max, max(1, int(img.height * ratio))),
            Image.Resampling.BILINEAR,
        )

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=qualite, optimize=False, subsampling=2)
    return buf.getvalue()


def _encoder_pil(largeur_max: int, qualite: int) -> bytes:
    from PIL import Image, ImageGrab

    geo = geometrie_ecran_actif()
    bbox = (
        geo["left"],
        geo["top"],
        geo["left"] + geo["width"],
        geo["top"] + geo["height"],
    )
    img = ImageGrab.grab(bbox=bbox)
    if img.width > largeur_max:
        ratio = largeur_max / img.width
        img = img.resize(
            (largeur_max, max(1, int(img.height * ratio))),
            Image.Resampling.BILINEAR,
        )
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=qualite, optimize=False)
    return buf.getvalue()


def capturer_jpeg(qualite: Optional[int] = None, largeur_max: Optional[int] = None) -> bytes:
    w, q, mon = _params()
    if largeur_max is not None:
        w = largeur_max
    if qualite is not None:
        q = qualite
    try:
        data = _encoder_mss(largeur_max=w, qualite=q, moniteur=mon)
    except Exception:
        data = _encoder_pil(largeur_max=w, qualite=q)
    try:
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        (SCREENSHOT_DIR / "latest.jpg").write_bytes(data)
    except Exception:
        pass
    return data


def _boucle_capture():
    global _latest_jpeg, _running
    interval = 1.0 / FPS_CIBLE
    sct = None
    Image = None
    try:
        import mss
        from PIL import Image as PilImage
        Image = PilImage
        sct = mss.mss()
    except Exception:
        sct = None

    while _running:
        if _clients <= 0:
            time.sleep(0.15)
            continue
        t0 = time.perf_counter()
        try:
            w, q, mon_idx = _params()
            if sct is not None and Image is not None:
                mons = sct.monitors
                idx = mon_idx if 0 < mon_idx < len(mons) else 1
                raw = sct.grab(mons[idx])
                img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                if img.width > w:
                    ratio = w / img.width
                    img = img.resize((w, max(1, int(img.height * ratio))), Image.Resampling.BILINEAR)
                buf = BytesIO()
                img.save(buf, format="JPEG", quality=q, optimize=False, subsampling=2)
                data = buf.getvalue()
            else:
                data = capturer_jpeg()
            with _lock:
                _latest_jpeg = data
        except Exception:
            time.sleep(0.02)
            continue
        reste = interval - (time.perf_counter() - t0)
        if reste > 0:
            time.sleep(reste)

    if sct is not None:
        try:
            sct.close()
        except Exception:
            pass


def demarrer_stream():
    global _thread, _running
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_boucle_capture, daemon=True, name="astat-screen")
    _thread.start()


def arreter_stream():
    global _running
    _running = False


def client_connecte():
    global _clients
    demarrer_stream()
    with _lock:
        _clients += 1


def client_deconnecte():
    global _clients
    with _lock:
        _clients = max(0, _clients - 1)


def frame_actuelle() -> Optional[bytes]:
    with _lock:
        return _latest_jpeg
