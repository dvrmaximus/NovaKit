"""Panel admin intégré au HUD (IA créateur)."""

from __future__ import annotations

import customtkinter as ctk

from ui.hud_theme import (
    ACCENT_DIM, BG_DEEP, BG_INPUT, BG_PANEL, LINE,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, SUCCESS,
)
from ui.hud_widgets import mono


class AdminHudPanel(ctk.CTkFrame):
    """Liste des utilisateurs + actions depuis le HUD admin."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_PANEL, corner_radius=10, border_width=1, border_color=LINE, **kw)
        ctk.CTkLabel(self, text="Admin", font=mono(12, True), text_color=TEXT_PRIMARY).pack(
            anchor="w", padx=12, pady=(10, 2)
        )
        ctk.CTkLabel(
            self, text="Utilisateurs de ton app", font=mono(9), text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=12, pady=(0, 8))

        self.liste = ctk.CTkScrollableFrame(self, fg_color=BG_DEEP, height=160, corner_radius=8)
        self.liste.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.sel = ctk.StringVar(value="")
        self.txt = ctk.CTkEntry(
            self, height=32, corner_radius=8, fg_color=BG_INPUT, border_color=LINE,
            text_color=TEXT_PRIMARY, font=mono(10), placeholder_text="Message / voix…",
        )
        self.txt.pack(fill="x", padx=10, pady=(0, 6))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))
        for label, act in (("Msg", "message"), ("Parler", "speak"), ("Ping", "ping")):
            ctk.CTkButton(
                row, text=label, width=64, height=28, corner_radius=6,
                font=mono(9), fg_color=ACCENT_DIM, hover_color=LINE, text_color=TEXT_PRIMARY,
                command=lambda a=act: self._cmd(a),
            ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            row, text="Refresh", width=64, height=28, corner_radius=6,
            font=mono(9), fg_color=BG_DEEP, hover_color=ACCENT_DIM, text_color=TEXT_SECONDARY,
            border_width=1, border_color=LINE, command=self.refresh,
        ).pack(side="right")

        self.status = ctk.CTkLabel(self, text="", font=mono(9), text_color=TEXT_MUTED)
        self.status.pack(anchor="w", padx=12, pady=(0, 8))
        self._users = []
        self.after(200, self.refresh)

    def refresh(self):
        for w in self.liste.winfo_children():
            w.destroy()
        try:
            from online.db import list_installs, init_db
            from online.admin_local import demarrer_admin_local
            demarrer_admin_local(ouvrir=False, reset_mdp=False)
            init_db()
            self._users = list_installs(80)
        except Exception as exc:
            self.status.configure(text=str(exc))
            return
        if not self._users:
            ctk.CTkLabel(self.liste, text="Aucun utilisateur", font=mono(10), text_color=TEXT_MUTED).pack(
                anchor="w", padx=6, pady=8
            )
            self.status.configure(text="0 compte")
            return
        for u in self._users:
            line = f"#{u.get('id')}  {u.get('pseudo') or '?'}  ·  {u.get('nom_ia') or '?'}  ·  {u.get('ip_public') or u.get('ip') or '—'}"
            btn = ctk.CTkButton(
                self.liste, text=line, anchor="w", height=28, corner_radius=6,
                font=mono(9), fg_color="transparent", hover_color=ACCENT_DIM,
                text_color=TEXT_SECONDARY,
                command=lambda i=u.get("id"): self.sel.set(str(i)),
            )
            btn.pack(fill="x", pady=1, padx=2)
        self.status.configure(text=f"{len(self._users)} utilisateur(s)", text_color=SUCCESS)

    def _cmd(self, action: str):
        sid = self.sel.get().strip()
        if not sid.isdigit():
            self.status.configure(text="Sélectionne un utilisateur")
            return
        uid = int(sid)
        user = next((u for u in self._users if u.get("id") == uid), None)
        if not user or not user.get("client_id"):
            self.status.configure(text="Pas de client_id (hors ligne / ancienne version)")
            return
        try:
            from online.db import enqueue_command
            enqueue_command(
                user["client_id"],
                action,
                {"text": self.txt.get().strip()},
                install_id=uid,
            )
            self.status.configure(text=f"Envoyé : {action} → #{uid}", text_color=SUCCESS)
        except Exception as exc:
            self.status.configure(text=str(exc))
