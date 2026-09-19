"""Capture audio système (loopback) → flux PCM pour le téléphone."""

from __future__ import annotations

import os
import threading
import time
from collections import deque

SAMPLE_RATE = 24000
CHUNK_MS = 40
BLOCK = int(SAMPLE_RATE * CHUNK_MS / 1000)

_lock = threading.Lock()
_clients = 0
_thread: threading.Thread | None = None
_stop = threading.Event()
_queue: deque[bytes] = deque(maxlen=50)
_erreur = ""
_device_name = ""


def audio_disponible() -> bool:
    try:
        import soundcard  # noqa: F401
        import numpy  # noqa: F401
        return True
    except ImportError:
        return False


def audio_config() -> dict:
    return {
        "sampleRate": SAMPLE_RATE,
        "channels": 1,
        "format": "s16le",
        "available": audio_disponible(),
        "error": _erreur,
        "device": _device_name,
    }


def client_audio_connecte():
    global _clients
    with _lock:
        _clients += 1
        if _clients == 1:
            _demarrer()


def client_audio_deconnecte():
    global _clients
    with _lock:
        _clients = max(0, _clients - 1)
        if _clients == 0:
            _arreter()


def chunk_actuel() -> bytes | None:
    with _lock:
        if not _queue:
            return None
        return _queue.popleft()


def _demarrer():
    global _thread, _erreur
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _erreur = ""
    _thread = threading.Thread(target=_boucle, daemon=True, name="astat-audio")
    _thread.start()


def _arreter():
    _stop.set()


def _choisir_loopback():
    """Choisit le meilleur périphérique loopback (sortie système)."""
    import soundcard as sc

    prefer = os.getenv("AUDIO_LOOPBACK", "").strip().lower()
    speaker = sc.default_speaker()
    candidats = []

    if speaker is not None:
        try:
            lb = sc.get_microphone(speaker.name, include_loopback=True)
            candidats.append(lb)
        except Exception:
            pass

    try:
        for m in sc.all_microphones(include_loopback=True):
            name = (m.name or "").lower()
            # Évite les vrais micros
            if any(x in name for x in ("microphone", "micro ", "mic (")):
                continue
            if prefer and prefer in name:
                candidats.insert(0, m)
            else:
                candidats.append(m)
    except Exception:
        pass

    # Priorité : Media / Speakers / moniteur / default
    def score(m):
        n = (m.name or "").lower()
        s = 0
        if prefer and prefer in n:
            s += 100
        if speaker and speaker.name and speaker.name.lower() in n:
            s += 50
        if "media" in n:
            s += 20
        if "haut-parleur" in n or "speaker" in n:
            s += 15
        if "gaming" in n:
            s += 10
        if "voicemeeter" in n and "out a1" in n:
            s += 25
        return s

    uniq = []
    seen = set()
    for m in candidats:
        key = getattr(m, "name", str(m))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(m)
    uniq.sort(key=score, reverse=True)
    return uniq[0] if uniq else None


def _boucle():
    global _erreur, _device_name
    try:
        import numpy as np
        import soundcard as sc  # noqa: F401
    except ImportError as exc:
        _erreur = f"Modules manquants : {exc}"
        return

    mic = _choisir_loopback()
    if mic is None:
        _erreur = "Aucun périphérique loopback trouvé"
        return

    _device_name = getattr(mic, "name", str(mic))
    # 1 ou 2 canaux max pour downmix mono
    ch_in = 1
    try:
        ch_in = min(2, int(getattr(mic, "channels", 2) or 2))
    except Exception:
        ch_in = 1

    try:
        with mic.recorder(samplerate=SAMPLE_RATE, channels=ch_in, blocksize=BLOCK) as rec:
            while not _stop.is_set():
                with _lock:
                    if _clients <= 0:
                        break
                try:
                    data = rec.record(numframes=BLOCK)
                except Exception as exc:
                    _erreur = str(exc)
                    time.sleep(0.2)
                    continue

                arr = np.asarray(data, dtype=np.float32)
                if arr.ndim == 2:
                    mono = arr.mean(axis=1)
                else:
                    mono = arr.reshape(-1)
                # Léger gain pour loopbacks faibles
                mono = np.clip(mono * 1.4, -1.0, 1.0)
                pcm = (mono * 32767.0).astype("<i2").tobytes()
                with _lock:
                    _queue.append(pcm)
    except Exception as exc:
        _erreur = f"Capture audio : {exc}"
        _device_name = ""
