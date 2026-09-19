import threading
from typing import Callable, Optional

from brain import AstatBrain
from local_commands import executer_commande_locale


class AstatHub:
    """Cerveau partagé entre le HUD PC et le contrôle mobile."""

    _instance: Optional["AstatHub"] = None

    def __init__(self):
        self.brain: Optional[AstatBrain] = None
        self._lock = threading.Lock()
        self._listeners: list[Callable] = []
        self.remote_clients = 0
        self.speak_enabled = True
        self.quota_bloque = False

    @classmethod
    def get(cls) -> "AstatHub":
        if cls._instance is None:
            cls._instance = AstatHub()
        return cls._instance

    def init_brain(self, brain: AstatBrain):
        self.brain = brain

    def on_message(self, callback: Callable):
        self._listeners.append(callback)

    def _notify(self, role: str, texte: str, source: str = "local"):
        for cb in self._listeners:
            try:
                cb(role, texte, source)
            except Exception:
                pass

    def process(self, message: str, source: str = "local") -> str:
        if not self.brain:
            raise RuntimeError("Astat non initialisé")
        with self._lock:
            self._notify("utilisateur", message, source)

            # 1) Commandes PC locales = instantané, sans quota Gemini
            local = executer_commande_locale(message)
            if local is not None:
                self._notify("astat", local, source)
                return local

            # 2) Sinon Gemini (si quota KO → message clair)
            if self.quota_bloque:
                texte = (
                    "Quota Gemini atteint sur toutes les clés. "
                    "Commandes PC toujours OK. "
                    "Ajoute des clés : GEMINI_API_KEYS=cle2,cle3 dans .env "
                    "(raccourci Nouvelle Cle Gemini)."
                )
                self._notify("astat", texte, source)
                return texte

            texte = self.brain.repondre(message)
            bas = texte.lower()
            if "quota" in bas or "satur" in bas or "429" in bas:
                self.quota_bloque = True
                local2 = executer_commande_locale(message)
                if local2 is not None:
                    texte = local2
                else:
                    texte = (
                        "Quota Gemini gratuit atteint. "
                        "Mode local actif : apps, volume, météo, mails, PC. "
                        "Chat libre indisponible jusqu'à demain ou nouvelle clé API "
                        "(raccourci : Nouvelle Cle Gemini sur le bureau)."
                    )
            self._notify("astat", texte, source)
            return texte
