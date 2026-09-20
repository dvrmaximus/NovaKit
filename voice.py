import asyncio
import os
import re
import tempfile

import edge_tts
import pygame
try:
    import speech_recognition as sr
except ImportError:
    sr = None

from config import VOIX_ASTAT, VOIX_RATE


def _texte_oral(texte: str, max_chars: int = 220) -> str:
    """Coupe pour la voix : plus court = plus rapide à générer/lire."""
    texte = (texte or "").strip()
    if len(texte) <= max_chars:
        return texte
    # Garde 1-2 phrases
    phrases = re.split(r"(?<=[.!?…])\s+", texte)
    acc = ""
    for p in phrases:
        if not p:
            continue
        if acc and len(acc) + len(p) + 1 > max_chars:
            break
        acc = f"{acc} {p}".strip() if acc else p
        if len(acc) >= 80:
            break
    return (acc or texte[:max_chars]).rstrip(".,;:") + "."


class AstatVoice:
    def __init__(self):
        pygame.mixer.init()
        self._busy = False

    async def _generer_audio(self, texte: str) -> str:
        fichier = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        fichier.close()
        communicate = edge_tts.Communicate(texte, voice=VOIX_ASTAT, rate=VOIX_RATE)
        await communicate.save(fichier.name)
        return fichier.name

    def parler(self, texte: str, attendre: bool = True):
        """Synthèse vocale. attendre=False = ne bloque pas (démarre et sort)."""
        oral = _texte_oral(texte)
        if not oral:
            return
        try:
            self._busy = True
            chemin = asyncio.run(self._generer_audio(oral))
            pygame.mixer.music.load(chemin)
            pygame.mixer.music.play()
            if attendre:
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(50)
                pygame.mixer.music.unload()
                try:
                    os.remove(chemin)
                except Exception:
                    pass
            else:
                # Nettoyage plus tard
                def _cleanup():
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(80)
                    try:
                        pygame.mixer.music.unload()
                        os.remove(chemin)
                    except Exception:
                        pass
                    self._busy = False
                import threading
                threading.Thread(target=_cleanup, daemon=True).start()
                return
        except Exception as erreur:
            print(f"[Erreur voix] {erreur}")
        finally:
            if attendre:
                self._busy = False

    @property
    def est_occupe(self) -> bool:
        if self._busy:
            return True
        try:
            return bool(pygame.mixer.get_init() and pygame.mixer.music.get_busy())
        except Exception:
            return False

    @staticmethod
    def ecouter(timeout: int = 4, phrase_limit: int = 8) -> str:
        if sr is None:
            raise RuntimeError("SpeechRecognition non installé")
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.25)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        return recognizer.recognize_google(audio, language="fr-FR")

    @staticmethod
    def bip_activation():
        try:
            import winsound
            winsound.Beep(880, 80)
        except Exception:
            pass
