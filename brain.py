import json
import time
from datetime import datetime

from google import genai
from google.genai import types

from config import API_KEY, API_KEYS, HISTORY_FILE, MODELE_GEMINI, instructions_systeme
from tools import ALL_TOOLS

MODELES_SECOURS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]


def _sauver_historique(role: str, texte: str):
    entree = {"role": role, "texte": texte, "date": datetime.now().isoformat()}
    historique = []
    if HISTORY_FILE.exists():
        try:
            historique = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            historique = []
    historique.append(entree)
    HISTORY_FILE.write_text(
        json.dumps(historique[-200:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _msg(erreur: Exception) -> str:
    return str(erreur).lower()


def _a_reessayer(erreur: Exception) -> bool:
    m = _msg(erreur)
    return any(
        x in m
        for x in (
            "429", "503", "quota", "unavailable", "high demand",
            "resource_exhausted", "not_found", "no longer available", "404",
            "overloaded", "try again later", "permission", "api key",
        )
    )


def _quota(erreur: Exception) -> bool:
    m = _msg(erreur)
    return "429" in m or "quota" in m or "resource_exhausted" in m


class AstatBrain:
    def __init__(self):
        self.cles = list(API_KEYS) if API_KEYS else ([API_KEY] if API_KEY else [])
        if not self.cles:
            raise ValueError(
                "Aucune clé API. Mets GEMINI_API_KEY ou GEMINI_API_KEYS=cle1,cle2 dans .env"
            )
        self.index_cle = 0
        self.client = genai.Client(api_key=self.cles[0])
        self.modeles = [MODELE_GEMINI] + [m for m in MODELES_SECOURS if m != MODELE_GEMINI]
        self.index_modele = 0
        self.modele = self.modeles[0]
        self.chat = self._creer_chat(self.modele)

    @property
    def cle_active(self) -> str:
        return self.cles[self.index_cle]

    def _creer_chat(self, modele: str):
        return self.client.chats.create(
            model=modele,
            config=types.GenerateContentConfig(
                system_instruction=instructions_systeme(),
                tools=ALL_TOOLS,
                max_output_tokens=512,
            ),
        )

    def _basculer_modele(self) -> bool:
        if self.index_modele + 1 >= len(self.modeles):
            return False
        self.index_modele += 1
        self.modele = self.modeles[self.index_modele]
        try:
            self.chat = self._creer_chat(self.modele)
            return True
        except Exception:
            return self._basculer_modele()

    def _basculer_cle(self) -> bool:
        """Passe à la clé API suivante (nouveau client + chat)."""
        if len(self.cles) <= 1:
            return False
        if self.index_cle + 1 >= len(self.cles):
            # Repart de la première (elles peuvent s'être remises)
            self.index_cle = 0
        else:
            self.index_cle += 1
        try:
            self.client = genai.Client(api_key=self.cles[self.index_cle])
            self.index_modele = 0
            self.modele = self.modeles[0]
            self.chat = self._creer_chat(self.modele)
            return True
        except Exception:
            return False

    def repondre(self, message: str) -> str:
        _sauver_historique("utilisateur", message)
        tentatives = max(3, len(self.cles) * 2)
        derniere = None

        for _ in range(tentatives):
            try:
                texte = self.chat.send_message(message).text or "Je n'ai pas pu formuler de réponse."
                _sauver_historique("astat", texte)
                return texte
            except Exception as erreur:
                derniere = erreur
                if not _a_reessayer(erreur):
                    texte = f"Erreur : {erreur}"
                    _sauver_historique("astat", texte)
                    return texte

                # 1) Autre modèle sur la même clé
                if self._basculer_modele():
                    time.sleep(0.3)
                    continue
                # 2) Autre clé API
                if self._basculer_cle():
                    time.sleep(0.3)
                    continue
                break

        if derniere and _quota(derniere):
            texte = (
                f"Toutes les clés Gemini sont en quota ({len(self.cles)} clé(s)). "
                "Ajoute d'autres clés dans .env (GEMINI_API_KEYS=cle1,cle2) "
                "ou attends demain. Mode local toujours actif pour le PC."
            )
        elif derniere and ("503" in _msg(derniere) or "unavailable" in _msg(derniere)):
            texte = "Gemini saturé. Réessaie dans quelques secondes."
        else:
            texte = f"Erreur : {derniere}"
        _sauver_historique("astat", texte)
        return texte
