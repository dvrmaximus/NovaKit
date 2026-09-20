"""Paramètres — HUD futuriste par catégories + couleur IA."""

from __future__ import annotations

import math
import tkinter as tk

import customtkinter as ctk

from config import KIT_NAME, ecrire_profil, lire_profil
import ui.hud_theme as theme
from ui.hud_theme import (
    PRESETS_COULEUR, appliquer_accent, est_hex_valide, normaliser_hex,
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

CATEGORIES = [
    ("compte", "Compte"),
    ("apparence", "Apparence"),
    ("voix", "Voix & modèle"),
    ("connexions", "Connexions"),
    ("securite", "Sécurité"),
    ("affichage", "Affichage"),
    ("sauvegarde", "Sauvegarde"),
]


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, on_saved=None, on_entrainer=None):
        super().__init__(master)
        self.on_saved = on_saved
        self.on_entrainer = on_entrainer
        self.title(f"{KIT_NAME} — Paramètres")
        self.geometry("780x620")
        self.minsize(700, 540)
        self.configure(fg_color=theme.BG_MAIN)
        ctk.set_appearance_mode("dark")

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
        self.v_ecran = ctk.StringVar(
            value="Principal" if mon in ("1", "primary") else "Secondaire"
        )
        couleur = normaliser_hex(p.get("couleur_ia") or p.get("accent_hex") or theme.ACCENT)
        self.v_couleur = ctk.StringVar(value=couleur)
        try:
            intensite = float(p.get("accent_intensite") or 1.0)
        except (TypeError, ValueError):
            intensite = 1.0
        self.v_intensite = ctk.DoubleVar(value=max(0.55, min(1.0, intensite)))
        self.v_discord_wh = ctk.StringVar(value=p.get("discord_webhook") or "")

        self._cat_btns: dict[str, ctk.CTkButton] = {}
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._preview_phase = 0.0
        self._preview_after = None
        self._orb = None
        self._did_save = False

        self._build_chrome()
        self._build_sidebar()
        self._build_pages()
        self._show("compte")

        self.bind("<Escape>", lambda e: self._fermer())
        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self.after(50, self.focus_force)
        self.after(80, self._tick_preview)

    def _build_chrome(self):
        head = ctk.CTkFrame(self, fg_color=theme.BG_DEEP, height=58, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left", padx=18, pady=10)
        ctk.CTkLabel(
            left, text="PARAMÈTRES", font=mono(18, True), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left, text="Configuration système · HUD", font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")
        # accent strip
        ctk.CTkFrame(head, fg_color=theme.ACCENT, width=3, corner_radius=0).place(
            x=0, y=0, relheight=1,
        )

        self.body = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        self.body.pack(fill="both", expand=True)

        foot = ctk.CTkFrame(self, fg_color=theme.BG_DEEP, height=60, corner_radius=0)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        self.msg = ctk.CTkLabel(foot, text="", font=mono(10), text_color=theme.ACCENT_SOFT)
        self.msg.pack(side="left", padx=18)
        ctk.CTkButton(
            foot, text="Fermer", width=90, height=34, corner_radius=8,
            font=mono(11), fg_color=theme.GLASS2, hover_color=theme.ACCENT_DIM,
            text_color=theme.TEXT_SECONDARY, command=self._fermer,
        ).pack(side="left", padx=(8, 0), pady=12)
        ctk.CTkButton(
            foot, text="Enregistrer", width=130, height=34, corner_radius=8,
            font=mono(11, True), fg_color=theme.ACCENT_DIM, hover_color=theme.LINE,
            text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.ACCENT,
            command=self._save,
        ).pack(side="right", padx=16, pady=12)
        ctk.CTkButton(
            foot, text="Sauver + relancer", width=140, height=34, corner_radius=8,
            font=mono(10), fg_color=theme.BG_PANEL, hover_color=theme.ACCENT_DIM,
            text_color=theme.TEXT_SECONDARY, border_width=1, border_color=theme.LINE,
            command=lambda: self._save(relancer=True),
        ).pack(side="right", padx=4, pady=12)

    def _build_sidebar(self):
        side = ctk.CTkFrame(self.body, fg_color=theme.BG_DEEP, width=168, corner_radius=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ctk.CTkLabel(
            side, text="CATÉGORIES", font=mono(8, True), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(16, 8))

        cats = list(CATEGORIES)
        if self._est_createur():
            cats.append(("admin", "Admin créateur"))

        for key, label in cats:
            btn = ctk.CTkButton(
                side, text=label, anchor="w", height=36, corner_radius=8,
                font=mono(11), fg_color="transparent", hover_color=theme.BG_PANEL,
                text_color=theme.TEXT_SECONDARY,
                command=lambda k=key: self._show(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._cat_btns[key] = btn

        self.content = ctk.CTkFrame(self.body, fg_color=theme.BG_MAIN, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

    def _build_pages(self):
        self._pages["compte"] = self._page_compte()
        self._pages["apparence"] = self._page_apparence()
        self._pages["voix"] = self._page_voix()
        self._pages["connexions"] = self._page_connexions()
        self._pages["securite"] = self._page_securite()
        self._pages["affichage"] = self._page_affichage()
        self._pages["sauvegarde"] = self._page_sauvegarde()
        if self._est_createur():
            self._pages["admin"] = self._page_admin()

    def _page(self) -> ctk.CTkScrollableFrame:
        return ctk.CTkScrollableFrame(
            self.content, fg_color=theme.BG_MAIN, corner_radius=0,
        )

    def _page_compte(self):
        sc = self._page()
        self._heading(sc, "Compte", "Identité locale et profil")
        self._entry(sc, "Pseudo", self.v_pseudo)
        self._entry(sc, "E-mail", self.v_email)
        self._entry(sc, "Nom de l'IA", self.v_nom)
        self._entry(sc, "Mot magique", self.v_mot)
        self._entry(sc, "Ville", self.v_ville)
        return sc

    def _page_apparence(self):
        sc = self._page()
        self._heading(sc, "Apparence", "Couleur de ton IA — aperçu en direct")

        preview_row = ctk.CTkFrame(sc, fg_color=theme.BG_PANEL, corner_radius=12,
                                   border_width=1, border_color=theme.LINE)
        preview_row.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(preview_row, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        orb_box = ctk.CTkFrame(inner, fg_color=theme.BG_DEEP, width=120, height=120, corner_radius=12)
        orb_box.pack(side="left", padx=(0, 16))
        orb_box.pack_propagate(False)
        self._orb = tk.Canvas(orb_box, width=110, height=110, bg=theme.BG_DEEP,
                              highlightthickness=0, bd=0)
        self._orb.pack(expand=True)

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(
            info, text="Couleur IA", font=mono(14, True), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")
        self._hex_lbl = ctk.CTkLabel(
            info, text=self.v_couleur.get(), font=mono(12), text_color=theme.ACCENT,
        )
        self._hex_lbl.pack(anchor="w", pady=(4, 8))
        ctk.CTkLabel(
            info, text="Presets ou code hex — le HUD suit cette teinte.",
            font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")

        ctk.CTkLabel(sc, text="Presets", font=mono(10, True), text_color=theme.TEXT_MUTED).pack(
            anchor="w", pady=(4, 6),
        )
        grid = ctk.CTkFrame(sc, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 12))
        for i, (name, hx) in enumerate(PRESETS_COULEUR):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=i // 4, column=i % 4, padx=4, pady=4, sticky="w")
            swatch = ctk.CTkButton(
                cell, text="", width=28, height=28, corner_radius=8,
                fg_color=hx, hover_color=hx, border_width=2,
                border_color=theme.LINE,
                command=lambda h=hx: self._set_couleur(h),
            )
            swatch.pack(side="left")
            ctk.CTkLabel(cell, text=name, font=mono(9), text_color=theme.TEXT_SECONDARY).pack(
                side="left", padx=6,
            )

        self._entry(sc, "Hex personnalisé", self.v_couleur)
        self.v_couleur.trace_add("write", lambda *_: self._on_couleur_edit())

        ctk.CTkLabel(sc, text="Intensité", font=mono(10), text_color=theme.TEXT_SECONDARY).pack(
            anchor="w",
        )
        self._int_lbl = ctk.CTkLabel(
            sc, text=f"{int(self.v_intensite.get() * 100)} %", font=mono(10),
            text_color=theme.TEXT_MUTED,
        )
        self._int_lbl.pack(anchor="e")
        slider = ctk.CTkSlider(
            sc, from_=0.55, to=1.0, number_of_steps=9,
            variable=self.v_intensite, progress_color=theme.ACCENT,
            button_color=theme.ACCENT_SOFT, button_hover_color=theme.ACCENT_HOT,
            fg_color=theme.BG_INPUT, height=16,
            command=self._on_intensite,
        )
        slider.pack(fill="x", pady=(2, 12))
        return sc

    def _page_voix(self):
        sc = self._page()
        self._heading(sc, "Voix & modèle", "Synthèse vocale et moteur Gemini")
        self._combo(sc, "Voix", self.v_voix, VOIX_FR)
        self._combo(sc, "Vitesse", self.v_rate, VITESSES)
        self._combo(sc, "Modèle", self.v_modele, MODELES)

        ctk.CTkLabel(
            sc, text="Réveil vocal", font=mono(12, True), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(16, 4))
        ctk.CTkLabel(
            sc,
            text="Enregistre comment TU prononces mon prénom (3–4 fois). "
                 "Je mémorise les transcriptions du micro pour mieux me réveiller.",
            font=mono(9), text_color=theme.TEXT_MUTED, wraplength=480, justify="left",
        ).pack(anchor="w", pady=(0, 8))
        try:
            from core.wake_training import statut_texte
            tip = statut_texte(self.v_nom.get().strip() or None)
        except Exception:
            tip = "Statut entraînement indisponible"
        self._wake_status = ctk.CTkLabel(
            sc, text=tip, font=mono(10), text_color=theme.ACCENT_SOFT,
        )
        self._wake_status.pack(anchor="w", pady=(0, 8))
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            row, text="Entraîner mon prénom", height=36, corner_radius=8, width=180,
            font=mono(11, True), fg_color=theme.ACCENT_DIM, hover_color=theme.LINE,
            text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.ACCENT,
            command=self._lancer_entrainement,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="Réinitialiser", height=36, corner_radius=8, width=110,
            font=mono(10), fg_color=theme.BG_PANEL, hover_color=theme.ACCENT_DIM,
            text_color=theme.TEXT_SECONDARY, border_width=1, border_color=theme.LINE,
            command=self._reset_entrainement,
        ).pack(side="left")
        return sc

    def _rafraichir_statut_wake(self):
        try:
            from core.wake_training import statut_texte
            tip = statut_texte(self.v_nom.get().strip() or None)
        except Exception:
            tip = "—"
        if getattr(self, "_wake_status", None):
            self._wake_status.configure(text=tip)

    def _lancer_entrainement(self):
        def _apres():
            self._rafraichir_statut_wake()
            self.msg.configure(text="Prénom entraîné.")

        if self.on_entrainer:
            try:
                self.on_entrainer(_apres)
            except TypeError:
                try:
                    self.on_entrainer()
                    self.after(1200, self._rafraichir_statut_wake)
                except Exception as exc:
                    self.msg.configure(text=f"Entraînement : {exc}")
            except Exception as exc:
                self.msg.configure(text=f"Entraînement : {exc}")
            return
        try:
            from ui.wake_enroll import ouvrir_entrainement
            ouvrir_entrainement(self, on_done=_apres)
        except Exception as exc:
            self.msg.configure(text=f"Entraînement : {exc}")

    def _reset_entrainement(self):
        try:
            from core.wake_training import reinitialiser
            reinitialiser()
            self._rafraichir_statut_wake()
            self.msg.configure(text="Entraînement du prénom effacé.")
        except Exception as exc:
            self.msg.configure(text=str(exc))

    def _page_connexions(self):
        sc = self._page()
        self._heading(sc, "Connexions", "Gmail et Discord (optionnel)")

        gmail_txt = "Non lié"
        try:
            from tools.gmail_tools import gmail_est_connecte
            if gmail_est_connecte():
                gmail_txt = "Connecté (token OAuth)"
        except Exception:
            pass
        ctk.CTkLabel(
            sc, text=f"Gmail : {gmail_txt}",
            font=mono(11), text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            sc,
            text="Dis « connecte Gmail » pour lier le compte (credentials.json OAuth "
                 "à la racine pour lire les mails ; sinon ouverture navigateur).",
            font=mono(9), text_color=theme.TEXT_MUTED, wraplength=480, justify="left",
        ).pack(anchor="w", pady=(0, 14))

        self._entry(sc, "Webhook Discord", self.v_discord_wh)
        ctk.CTkLabel(
            sc,
            text="URL discord.com/api/webhooks/… — pour « envoie sur Discord : … ». "
                 "Sans webhook : ouvrir Discord / liens seulement.",
            font=mono(9), text_color=theme.TEXT_MUTED, wraplength=480, justify="left",
        ).pack(anchor="w", pady=(0, 8))
        return sc

    def _page_securite(self):
        sc = self._page()
        self._heading(sc, "Sécurité", "PIN mobile et clé API")
        self._entry(sc, "PIN mobile", self.v_pin)
        self._entry(sc, "Clé Gemini", self.v_key, show="•")
        return sc

    def _page_affichage(self):
        sc = self._page()
        self._heading(sc, "Affichage", "Mode desktop, écran et tunnel")
        self._combo(sc, "HUD plein écran", self.v_desktop, ["Oui", "Non"])
        self._combo(sc, "Écran", self.v_ecran, ["Principal", "Secondaire"])
        self._combo(sc, "Tunnel mobile", self.v_tunnel, ["Oui", "Non"])
        return sc

    def _page_sauvegarde(self):
        sc = self._page()
        self._heading(sc, "Sauvegarde", "Archives ZIP du profil")
        self._combo(sc, "ZIP quotidien", self.v_backup, ["Oui", "Non"])
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x", pady=(4, 8))
        for label, cmd in (
            ("ZIP maintenant", self._backup_now),
            ("Exporter", self._export_bureau),
            ("Restaurer", self._restore_zip),
        ):
            ctk.CTkButton(
                row, text=label, height=34, corner_radius=8, width=120,
                font=mono(10), fg_color=theme.BG_PANEL, hover_color=theme.ACCENT_DIM,
                text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.LINE,
                command=cmd,
            ).pack(side="left", padx=(0, 8))
        return sc

    def _page_admin(self):
        sc = self._page()
        self._heading(sc, "Admin créateur", "Pilotage utilisateurs & IA")
        ctk.CTkLabel(
            sc,
            text="Panel local — identifiants dans data/admin_credentials.txt",
            font=mono(10), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 10))

        ctk.CTkButton(
            sc, text="Ouvrir le panel", height=40, corner_radius=8,
            font=mono(12, True), fg_color=theme.ACCENT_DIM, hover_color=theme.LINE,
            text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.ACCENT,
            command=self._ouvrir_admin,
        ).pack(fill="x", pady=(0, 8))
        return sc

    def _heading(self, parent, title: str, sub: str):
        ctk.CTkLabel(parent, text=title, font=mono(16, True), text_color=theme.TEXT_PRIMARY).pack(
            anchor="w", pady=(8, 2),
        )
        ctk.CTkLabel(parent, text=sub, font=mono(9), text_color=theme.TEXT_MUTED).pack(
            anchor="w", pady=(0, 14),
        )
        ctk.CTkFrame(parent, fg_color=theme.ACCENT, height=2, corner_radius=1).pack(
            fill="x", pady=(0, 14),
        )

    def _show(self, key: str):
        for k, page in self._pages.items():
            if k == key:
                page.pack(fill="both", expand=True, padx=18, pady=8)
            else:
                page.pack_forget()
        for k, btn in self._cat_btns.items():
            active = k == key
            btn.configure(
                fg_color=theme.ACCENT_DIM if active else "transparent",
                text_color=theme.ACCENT_HOT if active else theme.TEXT_SECONDARY,
                border_width=1 if active else 0,
                border_color=theme.ACCENT if active else theme.BG_DEEP,
            )

    def _set_couleur(self, hx: str):
        self.v_couleur.set(normaliser_hex(hx))
        self._preview_live()

    def _on_couleur_edit(self):
        self._preview_live()

    def _on_intensite(self, _val=None):
        self._int_lbl.configure(text=f"{int(self.v_intensite.get() * 100)} %")
        self._preview_live()

    def _preview_live(self):
        hx = self.v_couleur.get().strip()
        if not est_hex_valide(hx):
            return
        try:
            applied = appliquer_accent(hx, self.v_intensite.get())
            self._hex_lbl.configure(text=applied, text_color=theme.ACCENT)
        except Exception:
            pass

    def _tick_preview(self):
        self._preview_after = None
        try:
            if not self.winfo_exists() or self._orb is None:
                return
        except Exception:
            return
        c = self._orb
        c.delete("all")
        cx, cy = 55, 55
        self._preview_phase += 0.12
        breath = 1.0 + 0.06 * math.sin(self._preview_phase)
        r = int(28 * breath)
        glow = theme.ACCENT_GLOW
        accent = theme.ACCENT
        soft = theme.ACCENT_SOFT
        c.create_oval(cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18, outline=glow, width=2)
        c.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8, outline=theme.ACCENT_DIM, width=1)
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=accent, width=2, fill=theme.BG_DEEP)
        c.create_oval(cx - 8, cy - 8, cx + 8, cy + 8, fill=soft, outline="")
        a0 = (self._preview_phase * 50) % 360
        c.create_arc(
            cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3,
            start=a0, extent=80, style="arc", outline=theme.ACCENT_HOT, width=2,
        )
        self._preview_after = self.after(80, self._tick_preview)

    def _fermer(self):
        if self._preview_after is not None:
            try:
                self.after_cancel(self._preview_after)
            except Exception:
                pass
            self._preview_after = None
        if not self._did_save:
            try:
                from ui.hud_theme import charger_accent_profil
                charger_accent_profil()
            except Exception:
                pass
        self.destroy()

    def _est_createur(self) -> bool:
        try:
            from online.admin_local import est_createur
            return est_createur()
        except Exception:
            return False

    def _entry(self, parent, label: str, var, show: str | None = None):
        ctk.CTkLabel(parent, text=label, font=mono(10), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        kw = dict(
            textvariable=var, height=36, corner_radius=8,
            fg_color=theme.BG_INPUT, border_color=theme.LINE,
            text_color=theme.TEXT_PRIMARY, font=mono(11),
        )
        if show:
            kw["show"] = show
        ctk.CTkEntry(parent, **kw).pack(fill="x", pady=(3, 10))

    def _combo(self, parent, label: str, var, values: list):
        ctk.CTkLabel(parent, text=label, font=mono(10), text_color=theme.TEXT_SECONDARY).pack(anchor="w")
        ctk.CTkOptionMenu(
            parent, variable=var, values=values, height=36, corner_radius=8,
            fg_color=theme.BG_INPUT, button_color=theme.ACCENT_DIM,
            button_hover_color=theme.LINE, text_color=theme.TEXT_PRIMARY,
            font=mono(11), dropdown_font=mono(11),
        ).pack(fill="x", pady=(3, 10))

    def _backup_now(self):
        try:
            from core.backup import creer_sauvegarde
            path = creer_sauvegarde("manual")
            self.msg.configure(text=f"ZIP : {path.name}")
        except Exception as exc:
            self.msg.configure(text=str(exc))

    def _export_bureau(self):
        try:
            from core.backup import exporter_zip_bureau
            path = exporter_zip_bureau()
            self.msg.configure(text=f"Exporté : {path.name}")
        except Exception as exc:
            self.msg.configure(text=str(exc))

    def _restore_zip(self):
        try:
            from tkinter import filedialog
            from core.backup import restaurer_sauvegarde
            path = filedialog.askopenfilename(
                parent=self, title="Restaurer ZIP",
                filetypes=[("ZIP", "*.zip"), ("Tous", "*.*")],
            )
            if not path:
                return
            restaurer_sauvegarde(path)
            self.msg.configure(text="Restauré — enregistre + relance")
        except Exception as exc:
            self.msg.configure(text=str(exc))

    def _ouvrir_admin(self):
        try:
            from online.admin_local import demarrer_admin_local, infos_connexion, serveur_ok
            demarrer_admin_local(ouvrir=True, reset_mdp=True)
            info = infos_connexion()
            self.msg.configure(
                text=f"{info['url']} — {info['username']} / {info['password']}"
                if serveur_ok() else "Serveur admin pas prêt"
            )
        except Exception as exc:
            self.msg.configure(text=str(exc))

    def _save(self, relancer: bool = False):
        nom = self.v_nom.get().strip() or "Nova"
        pin = "".join(c for c in self.v_pin.get() if c.isdigit())
        if len(pin) < 4:
            self.msg.configure(text="PIN : 4 chiffres min.")
            return
        key = self.v_key.get().strip()
        if not key:
            self.msg.configure(text="Clé Gemini obligatoire.")
            return
        email = self.v_email.get().strip().lower()
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            self.msg.configure(text="E-mail invalide.")
            return
        couleur = normaliser_hex(self.v_couleur.get(), "#4EC9D4")
        intensite = f"{self.v_intensite.get():.2f}"
        mon = "primary" if self.v_ecran.get().startswith("Principal") else "secondary"
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
            "couleur_ia": couleur,
            "accent_hex": couleur,
            "accent_intensite": intensite,
            "discord_webhook": self.v_discord_wh.get().strip(),
        })
        appliquer_accent(couleur, float(intensite))
        self._did_save = True
        self.msg.configure(text="Enregistré.")
        if self._preview_after is not None:
            try:
                self.after_cancel(self._preview_after)
            except Exception:
                pass
            self._preview_after = None
        if self.on_saved:
            try:
                self.on_saved(relancer=relancer)
            except TypeError:
                self.on_saved()
        if relancer:
            self.destroy()
            return
        self.after(700, self.destroy)


def ouvrir_parametres(master, on_saved=None, on_entrainer=None):
    win = SettingsWindow(master, on_saved=on_saved, on_entrainer=on_entrainer)
    try:
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(350, lambda: win.attributes("-topmost", False))
    except Exception:
        pass
    return win
