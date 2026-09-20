"""Fenêtre discussion simple avec l'IA (multi-tours)."""

from __future__ import annotations

import threading

import customtkinter as ctk

from config import MOT_MAGIQUE, NOM_IA, NOM_IA_AFFICHE
from core.hub import AstatHub
from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_SOFT, BG_DEEP, BG_INPUT, BG_MAIN,
    BUBBLE_ASTAT, BUBBLE_USER, GLASS, GLASS2, GLASS_BORDER, LINE,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)
from ui.hud_widgets import mono


class ChatWindow(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title(f"Discussion · {NOM_IA_AFFICHE}")
        self.geometry("520x640")
        self.minsize(400, 480)
        self.configure(fg_color=BG_MAIN)
        self.hub = AstatHub.get()
        self.processing = False

        head = ctk.CTkFrame(self, fg_color=BG_DEEP, height=56, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(
            head, text=NOM_IA_AFFICHE, font=mono(16, True), text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(
            head, text="Discussion", font=mono(10), text_color=TEXT_MUTED,
        ).pack(side="left", pady=18)
        self.status = ctk.CTkLabel(head, text="prêt", font=mono(10), text_color=TEXT_MUTED)
        self.status.pack(side="right", padx=16)

        self.zone = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.zone.pack(fill="both", expand=True, padx=12, pady=10)

        barre = ctk.CTkFrame(self, fg_color=BG_DEEP, height=64, corner_radius=0)
        barre.pack(fill="x")
        barre.pack_propagate(False)
        inner = ctk.CTkFrame(barre, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=12)
        self.entry = ctk.CTkEntry(
            inner,
            placeholder_text=f"Parle à {NOM_IA}…",
            height=36, corner_radius=8,
            fg_color=BG_INPUT, border_color=LINE, text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self._envoyer)
        ctk.CTkButton(
            inner, text="Envoyer", width=90, height=36, corner_radius=8,
            font=mono(11), fg_color=ACCENT_DIM, hover_color=LINE,
            text_color=TEXT_PRIMARY, command=self._envoyer,
        ).pack(side="left")

        self._bulle(
            "astat",
            f"Salut — je suis {NOM_IA}. Pose-moi une question ou donne un ordre "
            f"(« ouvre Chrome », « quelle heure… »). Mot magique vocal : « {MOT_MAGIQUE} ».",
        )
        self.after(100, self.entry.focus)

    def _bulle(self, role: str, texte: str):
        est_ia = role == "astat"
        box = ctk.CTkFrame(self.zone, fg_color="transparent")
        box.pack(fill="x", pady=5)
        ctk.CTkLabel(
            box,
            text=NOM_IA_AFFICHE if est_ia else "Toi",
            font=mono(9, True),
            text_color=TEXT_SECONDARY if est_ia else TEXT_MUTED,
        ).pack(anchor="w" if est_ia else "e")
        bubble = ctk.CTkFrame(
            box,
            fg_color=BUBBLE_ASTAT if est_ia else BUBBLE_USER,
            corner_radius=12,
            border_width=1,
            border_color=GLASS_BORDER if est_ia else LINE,
        )
        bubble.pack(anchor="w" if est_ia else "e", fill="x", pady=(2, 0))
        ctk.CTkLabel(
            bubble, text=texte, font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=TEXT_PRIMARY, justify="left", wraplength=420, anchor="w",
        ).pack(padx=12, pady=10, anchor="w")
        self.after(40, lambda: self.zone._parent_canvas.yview_moveto(1.0))

    def _envoyer(self, event=None):
        msg = self.entry.get().strip()
        if not msg or self.processing:
            return
        self.entry.delete(0, "end")
        self._bulle("user", msg)
        self.processing = True
        self.status.configure(text="réfléchit…")
        threading.Thread(target=self._traiter, args=(msg,), daemon=True).start()

    def _traiter(self, msg: str):
        try:
            # Discussion libre : passe directement au cerveau (évite de court-circuiter
            # les petites phrases type "salut" par des commandes locales trop agressives)
            from local_commands import executer_commande_locale
            local = executer_commande_locale(msg)
            if local is not None and self._ressemble_commande(msg):
                texte = local
            else:
                if not self.hub.brain:
                    texte = "Cerveau non prêt."
                else:
                    texte = self.hub.brain.repondre(msg)
        except Exception as exc:
            texte = f"Erreur : {exc}"
        self.processing = False
        self.after(0, self._afficher_reponse, texte)

    @staticmethod
    def _ressemble_commande(msg: str) -> bool:
        t = msg.lower().strip()
        cles = (
            "ouvre", "ouvrir", "lance", "lancer", "volume", "verrouill", "éteins", "eteins",
            "meteo", "météo", "heure", "mail", "gmail", "google", "discord", "youtube",
            "you tube", "capture", "veille", "connecte", "connecter", "lie mon", "lier ",
            "spotify", "chrome", "steam", "envoie sur discord", "envoyer sur discord",
            "liste utilisateur", "message a", "message à", "fais parler",
            "ping ", "status ", "statut ",
        )
        return any(t.startswith(c) or f" {c}" in t for c in cles)

    def _afficher_reponse(self, texte: str):
        self._bulle("astat", texte)
        self.status.configure(text="prêt")
        try:
            from voice import AstatVoice
            AstatVoice().parler(texte, attendre=False)
        except Exception:
            pass


def ouvrir_discussion(master=None):
    win = ChatWindow(master)
    win.focus()
    return win
