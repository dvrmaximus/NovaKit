"""Wizard simple — 3 étapes."""

from __future__ import annotations

import customtkinter as ctk

from config import KIT_NAME, KIT_VERSION, ecrire_profil
from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_SOFT, BG_DEEP, BG_INPUT, BG_MAIN,
    GLASS, GLASS2, GLASS_BORDER, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)
from ui.hud_widgets import mono

SUGGESTIONS = ["Nova", "Aria", "Atlas", "Echo", "Jarvis", "Nyx"]


class SetupWizard(ctk.CTk):
    def __init__(self, on_termine=None):
        super().__init__()
        self.on_termine = on_termine
        self.title(f"{KIT_NAME} — Inscription")
        self.geometry("640x520")
        self.minsize(560, 460)
        self.configure(fg_color=BG_MAIN)
        ctk.set_appearance_mode("dark")

        self.step = 0
        self.vars = {
            "pseudo": ctk.StringVar(value=""),
            "nom_ia": ctk.StringVar(value="Nova"),
            "api_key": ctk.StringVar(value=""),
            "ville": ctk.StringVar(value="Paris"),
            "pin": ctk.StringVar(value="2809"),
        }

        self.font_title = mono(26, True)
        self.font_h = mono(13, True)
        self.font_b = mono(12)
        self.font_s = mono(10)

        head = ctk.CTkFrame(self, fg_color=BG_DEEP, height=64, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text=f"◈ {KIT_NAME}", font=self.font_title, text_color=ACCENT).pack(
            side="left", padx=22, pady=14
        )
        self.step_lbl = ctk.CTkLabel(head, text="1 / 3", font=self.font_h, text_color=ACCENT_SOFT)
        self.step_lbl.pack(side="right", padx=22)

        self.body = ctk.CTkFrame(self, fg_color=BG_MAIN, corner_radius=0)
        self.body.pack(fill="both", expand=True, padx=26, pady=16)

        foot = ctk.CTkFrame(self, fg_color=BG_DEEP, height=60, corner_radius=0)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        self.btn_back = ctk.CTkButton(
            foot, text="←", width=48, height=34, corner_radius=8,
            font=self.font_b, fg_color=GLASS2, hover_color=ACCENT_DIM,
            text_color=TEXT_SECONDARY, command=self._prev, state="disabled",
        )
        self.btn_back.pack(side="left", padx=20, pady=12)
        self.btn_next = ctk.CTkButton(
            foot, text="SUIVANT →", width=140, height=34, corner_radius=8,
            font=self.font_h, fg_color=ACCENT_DIM, hover_color=ACCENT,
            text_color=BG_DEEP, command=self._next,
        )
        self.btn_next.pack(side="right", padx=20, pady=12)
        self.err = ctk.CTkLabel(foot, text="", font=self.font_s, text_color="#FF6B7A")
        self.err.pack(side="right", padx=6)

        self._render()

    def _clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def _render(self):
        self._clear()
        self.err.configure(text="")
        self.step_lbl.configure(text=f"{self.step + 1} / 3")
        self.btn_back.configure(state="normal" if self.step > 0 else "disabled")
        self.btn_next.configure(text="LANCER →" if self.step == 2 else "SUIVANT →")
        [self._p1, self._p2, self._p3][self.step]()

    def _field(self, label, var, placeholder="", show=None):
        ctk.CTkLabel(self.body, text=label, font=self.font_s, text_color=TEXT_MUTED).pack(anchor="w")
        kw = dict(
            textvariable=var, height=40, corner_radius=10,
            fg_color=BG_INPUT, border_color=ACCENT_DIM, text_color=TEXT_PRIMARY,
            font=self.font_b, placeholder_text=placeholder,
        )
        if show is not None:
            kw["show"] = show
        ctk.CTkEntry(self.body, **kw).pack(fill="x", pady=(4, 12))

    def _p1(self):
        ctk.CTkLabel(self.body, text="Créer ton IA", font=self.font_title, text_color=TEXT_PRIMARY).pack(
            anchor="w", pady=(4, 6)
        )
        ctk.CTkLabel(
            self.body, text="Deux infos suffisent pour commencer.",
            font=self.font_b, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 14))
        self._field("TON PRÉNOM / PSEUDO", self.vars["pseudo"], "Alex")
        self._field("NOM DE TON IA", self.vars["nom_ia"], "Nova")
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x")
        for nom in SUGGESTIONS:
            ctk.CTkButton(
                row, text=nom, width=72, height=28, corner_radius=8,
                font=self.font_s, fg_color=GLASS2, hover_color=ACCENT_DIM,
                text_color=ACCENT_SOFT, border_width=1, border_color=GLASS_BORDER,
                command=lambda n=nom: self.vars["nom_ia"].set(n),
            ).pack(side="left", padx=3)

    def _p2(self):
        ctk.CTkLabel(self.body, text="Clé Gemini", font=self.font_title, text_color=TEXT_PRIMARY).pack(
            anchor="w", pady=(4, 6)
        )
        ctk.CTkLabel(
            self.body,
            text="Gratuite sur Google AI Studio (1 minute).",
            font=self.font_b, text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 8))
        ctk.CTkButton(
            self.body, text="Ouvrir aistudio.google.com/apikey", height=34, corner_radius=8,
            font=self.font_s, fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=lambda: __import__("webbrowser").open("https://aistudio.google.com/apikey"),
        ).pack(anchor="w", pady=(0, 14))
        self._field("COLLE TA CLÉ ICI", self.vars["api_key"], "AIza…", show="*")

    def _p3(self):
        ctk.CTkLabel(self.body, text="Presque prêt", font=self.font_title, text_color=TEXT_PRIMARY).pack(
            anchor="w", pady=(4, 6)
        )
        self._field("VILLE", self.vars["ville"], "Paris")
        self._field("PIN TÉLÉPHONE (4 chiffres)", self.vars["pin"], "2809")
        nom = self.vars["nom_ia"].get().strip() or "Nova"
        card = ctk.CTkFrame(self.body, fg_color=GLASS, corner_radius=12, border_width=1, border_color=GLASS_BORDER)
        card.pack(fill="x", pady=10)
        ctk.CTkLabel(
            card,
            text=f"Tu vas discuter avec {nom}.\nBouton DISCUSSION sur le HUD après le lancement.",
            font=self.font_b, text_color=TEXT_SECONDARY, justify="left",
        ).pack(anchor="w", padx=14, pady=12)

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._render()

    def _next(self):
        if self.step == 0:
            if len(self.vars["pseudo"].get().strip()) < 2:
                self.err.configure(text="Indique ton prénom")
                return
            if len(self.vars["nom_ia"].get().strip()) < 2:
                self.err.configure(text="Choisis un nom d'IA")
                return
        if self.step == 1:
            if len(self.vars["api_key"].get().strip()) < 10:
                self.err.configure(text="Clé Gemini obligatoire")
                return
        if self.step == 2:
            pin = self.vars["pin"].get().strip()
            if not pin.isdigit() or len(pin) < 4:
                self.err.configure(text="PIN : 4 chiffres min.")
                return
            self._finir()
            return
        self.step += 1
        self._render()

    def _finir(self):
        nom = self.vars["nom_ia"].get().strip()
        profil = {
            "pseudo": self.vars["pseudo"].get().strip(),
            "nom_ia": nom,
            "mot_magique": nom.lower(),
            "api_key": self.vars["api_key"].get().strip(),
            "ville": self.vars["ville"].get().strip() or "Paris",
            "pin": self.vars["pin"].get().strip(),
            "voix": "fr-FR-DeniseNeural",
            "desktop_mode": "true",
            "enable_tunnel": "false",
        }
        ecrire_profil(profil)
        try:
            from core.notify_creator import notifier_setup
            notifier_setup(profil)
        except Exception:
            pass
        self.destroy()


def lancer_setup(on_termine=None):
    wiz = SetupWizard(on_termine=on_termine)
    wiz.mainloop()
    if on_termine and callable(on_termine):
        try:
            from config import est_configure
            if est_configure():
                on_termine()
        except Exception:
            on_termine()
