"""Config créateur — inscriptions + mises à jour + online."""

from __future__ import annotations

import customtkinter as ctk

from core.notify_creator import charger_creator, sauver_creator
from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_SOFT, BG_DEEP, BG_INPUT, BG_MAIN,
    GLASS2, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)
from ui.hud_widgets import mono


class CreatorConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NovaKit — Config créateur")
        self.geometry("640x560")
        self.configure(fg_color=BG_MAIN)
        ctk.set_appearance_mode("dark")
        cfg = charger_creator()

        ctk.CTkLabel(
            self, text="◈ Config créateur", font=mono(22, True), text_color=ACCENT,
        ).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(
            self,
            text="Remplis ça avant de partager. Lance aussi « Systeme Online.bat ».",
            font=mono(11), text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        self.form = ctk.StringVar(value=cfg.get("inscription_email_form") or cfg.get("formspree") or "")
        self.update_url = ctk.StringVar(value=cfg.get("update_check_url") or "")
        self.online = ctk.StringVar(value=cfg.get("online_api_url") or "")
        self.name = ctk.StringVar(value=cfg.get("creator_name") or "Lutre")

        self._ligne("Ton prénom (créateur)", self.name, "Lutre")
        self._ligne(
            "1) Système online (panel admin) — auto si tu lances Systeme Online.bat",
            self.online,
            "https://xxxx.trycloudflare.com",
        )
        self._ligne(
            "2) Inscriptions mail → Formspree (optionnel)",
            self.form,
            "https://formspree.io/f/xxxxxx",
        )
        self._ligne(
            "3) Mises à jour → URL de ton version.json",
            self.update_url,
            "https://raw.githubusercontent.com/dvrmaximus/NovaKit/main/version.json",
        )

        self.msg = ctk.CTkLabel(self, text="", font=mono(10), text_color=ACCENT_SOFT)
        self.msg.pack(anchor="w", padx=24)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=16)
        ctk.CTkButton(
            row, text="OUVRIR FORMSPREE", height=36, corner_radius=8,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=lambda: __import__("webbrowser").open("https://formspree.io"),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="ENREGISTRER", height=36, corner_radius=8, width=140,
            font=mono(12, True), fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=BG_DEEP,
            command=self._save,
        ).pack(side="right")

    def _ligne(self, label, var, placeholder):
        ctk.CTkLabel(self, text=label, font=mono(10, True), text_color=TEXT_MUTED).pack(
            anchor="w", padx=24
        )
        ctk.CTkEntry(
            self, textvariable=var, height=38, corner_radius=10,
            fg_color=BG_INPUT, border_color=ACCENT_DIM, text_color=TEXT_PRIMARY,
            font=mono(11), placeholder_text=placeholder,
        ).pack(fill="x", padx=24, pady=(4, 8))

    def _save(self):
        sauver_creator({
            "creator_name": self.name.get().strip() or "Créateur",
            "inscription_email_form": self.form.get().strip(),
            "update_check_url": self.update_url.get().strip(),
            "online_api_url": self.online.get().strip().rstrip("/"),
            "enabled": True,
        })
        self.msg.configure(text="Enregistré.")


def lancer_config_createur():
    app = CreatorConfigApp()
    app.mainloop()


if __name__ == "__main__":
    lancer_config_createur()
