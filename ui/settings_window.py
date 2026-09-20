"""Fenêtre paramètres — bases du profil NovaKit."""

from __future__ import annotations

import customtkinter as ctk

from config import KIT_NAME, ecrire_profil, lire_profil
from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_SOFT, BG_DEEP, BG_INPUT, BG_MAIN,
    GLASS2, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)
from ui.hud_widgets import mono

VOIX_FR = [
    "fr-FR-DeniseNeural",
    "fr-FR-HenriNeural",
    "fr-FR-EloiseNeural",
    "fr-FR-RemyMultilingualNeural",
    "fr-FR-VivienneMultilingualNeural",
]

MODELES = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

VITESSES = ["-10%", "+0%", "+10%", "+20%", "+30%", "+40%"]


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.title(f"{KIT_NAME} — Paramètres")
        self.geometry("520x720")
        self.minsize(480, 600)
        self.configure(fg_color=BG_MAIN)
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        p = lire_profil()
        self.v_nom = ctk.StringVar(value=p["nom_ia"])
        self.v_mot = ctk.StringVar(value=p["mot_magique"])
        self.v_ville = ctk.StringVar(value=p["ville"])
        self.v_pin = ctk.StringVar(value=p["pin"])
        self.v_key = ctk.StringVar(value=p["api_key"])
        self.v_email = ctk.StringVar(value=p.get("email") or "")
        self.v_pseudo = ctk.StringVar(value=p.get("pseudo") or "")
        self.v_backup = ctk.StringVar(value="Oui" if p.get("backup_daily", "true") == "true" else "Non")
        self.v_voix = ctk.StringVar(value=p["voix"] if p["voix"] in VOIX_FR else VOIX_FR[0])
        self.v_rate = ctk.StringVar(value=p["voix_rate"] if p["voix_rate"] in VITESSES else "+20%")
        self.v_modele = ctk.StringVar(value=p["modele"] if p["modele"] in MODELES else MODELES[0])
        self.v_tunnel = ctk.StringVar(value="Oui" if p["enable_tunnel"] == "true" else "Non")
        self.v_desktop = ctk.StringVar(value="Oui" if p["desktop_mode"] == "true" else "Non")
        mon = p["desktop_monitor"]
        if mon in ("1", "primary"):
            mon_lbl = "Principal"
        elif mon in ("2", "secondary"):
            mon_lbl = "Secondaire"
        else:
            mon_lbl = "Secondaire"
        self.v_ecran = ctk.StringVar(value=mon_lbl)

        head = ctk.CTkFrame(self, fg_color=BG_DEEP, height=56, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(head, text="◈ Paramètres", font=mono(20, True), text_color=ACCENT).pack(
            side="left", padx=18, pady=12
        )
        ctk.CTkLabel(head, text="bases du profil", font=mono(10), text_color=TEXT_MUTED).pack(
            side="left", padx=4, pady=16
        )

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG_MAIN, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=16, pady=10)

        self._section(scroll, "Compte")
        self._entry(scroll, "Pseudo", self.v_pseudo)
        self._entry(scroll, "E-mail (inscription + sauvegardes)", self.v_email)

        self._section(scroll, "Identité")
        self._entry(scroll, "Nom de l'IA", self.v_nom)
        self._entry(scroll, "Mot magique (écoute vocale)", self.v_mot)
        self._entry(scroll, "Ville (météo)", self.v_ville)

        self._section(scroll, "Sécurité & IA")
        self._entry(scroll, "PIN téléphone (4+ chiffres)", self.v_pin)
        self._entry(scroll, "Clé API Gemini", self.v_key, show="•")
        self._combo(scroll, "Modèle Gemini", self.v_modele, MODELES)

        self._section(scroll, "Voix")
        self._combo(scroll, "Voix", self.v_voix, VOIX_FR)
        self._combo(scroll, "Vitesse", self.v_rate, VITESSES)

        self._section(scroll, "Affichage & remote")
        self._combo(scroll, "Mode fond d'écran (HUD)", self.v_desktop, ["Oui", "Non"])
        self._combo(scroll, "Écran HUD", self.v_ecran, ["Principal", "Secondaire"])
        self._combo(scroll, "Tunnel Internet (mobile)", self.v_tunnel, ["Oui", "Non"])

        self._section(scroll, "Sauvegarde ZIP")
        self._combo(scroll, "Sauvegarde auto chaque jour", self.v_backup, ["Oui", "Non"])
        try:
            from core.backup import derniere_sauvegarde, lister_sauvegardes
            last = derniere_sauvegarde() or "jamais"
            n = len(lister_sauvegardes())
            ctk.CTkLabel(
                scroll,
                text=f"Dernière : {last}  ·  {n} archive(s) dans data/backups",
                font=mono(9), text_color=TEXT_MUTED,
            ).pack(anchor="w", pady=(0, 6))
        except Exception:
            pass
        row_b = ctk.CTkFrame(scroll, fg_color="transparent")
        row_b.pack(fill="x", pady=(0, 4))
        ctk.CTkButton(
            row_b, text="ZIP MAINTENANT", height=34, corner_radius=8, width=140,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=self._backup_now,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            row_b, text="EXPORTER SUR BUREAU", height=34, corner_radius=8,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=self._export_bureau,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            scroll, text="RESTAURER DEPUIS UN ZIP…", height=34, corner_radius=8,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=TEXT_SECONDARY,
            command=self._restore_zip,
        ).pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(
            scroll,
            text="Les MAJ gardent ton compte (.env, Gmail, notes). Le ZIP sert de filet de sécurité.",
            font=mono(9), text_color=TEXT_MUTED, wraplength=440, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        self.msg = ctk.CTkLabel(self, text="", font=mono(10), text_color=ACCENT_SOFT)
        self.msg.pack(anchor="w", padx=18)

        foot = ctk.CTkFrame(self, fg_color=BG_DEEP, height=58, corner_radius=0)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        ctk.CTkButton(
            foot, text="FERMER", width=100, height=34, corner_radius=8,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=TEXT_SECONDARY,
            command=self.destroy,
        ).pack(side="left", padx=16, pady=12)
        ctk.CTkButton(
            foot, text="ENREGISTRER", width=140, height=34, corner_radius=8,
            font=mono(12, True), fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=BG_DEEP,
            command=self._save,
        ).pack(side="right", padx=16, pady=12)
        ctk.CTkButton(
            foot, text="SAUVER + RELANCER", width=150, height=34, corner_radius=8,
            font=mono(11), fg_color=GLASS2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=lambda: self._save(relancer=True),
        ).pack(side="right", padx=4, pady=12)

        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _section(self, parent, title: str):
        ctk.CTkLabel(
            parent, text=title.upper(), font=mono(10, True), text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(12, 4))

    def _entry(self, parent, label: str, var, show: str | None = None):
        ctk.CTkLabel(parent, text=label, font=mono(10), text_color=TEXT_PRIMARY).pack(anchor="w")
        kw = dict(
            textvariable=var, height=34, corner_radius=8,
            fg_color=BG_INPUT, border_color=ACCENT_DIM, text_color=TEXT_PRIMARY, font=mono(11),
        )
        if show:
            kw["show"] = show
        ctk.CTkEntry(parent, **kw).pack(fill="x", pady=(2, 8))

    def _combo(self, parent, label: str, var, values: list):
        ctk.CTkLabel(parent, text=label, font=mono(10), text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkOptionMenu(
            parent, variable=var, values=values, height=34, corner_radius=8,
            fg_color=BG_INPUT, button_color=ACCENT_DIM, button_hover_color=ACCENT,
            text_color=TEXT_PRIMARY, font=mono(11), dropdown_font=mono(11),
        ).pack(fill="x", pady=(2, 8))

    def _backup_now(self):
        try:
            from core.backup import creer_sauvegarde
            path = creer_sauvegarde("manual")
            self.msg.configure(text=f"ZIP OK — {path.name}")
        except Exception as exc:
            self.msg.configure(text=f"Erreur sauvegarde : {exc}")

    def _export_bureau(self):
        try:
            from core.backup import exporter_zip_bureau
            path = exporter_zip_bureau()
            self.msg.configure(text=f"Exporté : {path.name} (Bureau)")
        except Exception as exc:
            self.msg.configure(text=f"Export : {exc}")

    def _restore_zip(self):
        try:
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=self,
                title="Restaurer NovaKit depuis un ZIP",
                filetypes=[("Archives ZIP", "*.zip"), ("Tous", "*.*")],
            )
            if not path:
                return
            from core.backup import restaurer_sauvegarde
            restaurer_sauvegarde(path)
            self.msg.configure(text="Restauré — clique SAUVER + RELANCER")
            if self.on_saved:
                try:
                    self.on_saved(relancer=True)
                except TypeError:
                    self.on_saved()
            self.after(600, self.destroy)
        except Exception as exc:
            self.msg.configure(text=f"Restauration : {exc}")

    def _save(self, relancer: bool = False):
        nom = self.v_nom.get().strip() or "Nova"
        pin = "".join(c for c in self.v_pin.get() if c.isdigit())
        if len(pin) < 4:
            self.msg.configure(text="PIN : au moins 4 chiffres.")
            return
        key = self.v_key.get().strip()
        if not key:
            self.msg.configure(text="Clé Gemini obligatoire.")
            return
        email = self.v_email.get().strip().lower()
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            self.msg.configure(text="E-mail invalide.")
            return
        ecran = self.v_ecran.get()
        mon = "primary" if ecran.startswith("Principal") else "secondary"
        ecrire_profil({
            "nom_ia": nom,
            "mot_magique": (self.v_mot.get().strip() or nom).lower(),
            "ville": self.v_ville.get().strip() or "Paris",
            "pin": pin,
            "api_key": key,
            "email": email,
            "pseudo": self.v_pseudo.get().strip() or nom,
            "backup_daily": "true" if self.v_backup.get() == "Oui" else "false",
            "voix": self.v_voix.get(),
            "voix_rate": self.v_rate.get(),
            "modele": self.v_modele.get(),
            "enable_tunnel": "true" if self.v_tunnel.get() == "Oui" else "false",
            "desktop_mode": "true" if self.v_desktop.get() == "Oui" else "false",
            "desktop_monitor": mon,
        })
        self.msg.configure(text="Enregistré.")
        if self.on_saved:
            try:
                self.on_saved(relancer=relancer)
            except TypeError:
                self.on_saved()
        if relancer:
            self.destroy()
            return
        self.after(1200, self.destroy)


def ouvrir_parametres(master, on_saved=None):
    win = SettingsWindow(master, on_saved=on_saved)
    win.grab_set()
    return win
