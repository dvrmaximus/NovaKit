"""Modal guidé — entraîner la prononciation du prénom de l'IA."""

from __future__ import annotations

import threading

import customtkinter as ctk

from config import NOM_IA
from core import wake_training as wt
import ui.hud_theme as theme
from ui.hud_widgets import mono
from voice import AstatVoice


class WakeEnrollWindow(ctk.CTkToplevel):
    def __init__(self, master, voice: AstatVoice | None = None, on_done=None, on_phase=None):
        super().__init__(master)
        self.voice = voice or AstatVoice()
        self.on_done = on_done
        self.on_phase = on_phase  # callable("enrolling"|"done"|None)
        self._busy = False
        self._cancel = False

        self.title("Entraîner mon prénom")
        self.geometry("460x420")
        self.minsize(420, 380)
        self.configure(fg_color=theme.BG_MAIN)
        ctk.set_appearance_mode("dark")

        data = wt.charger()
        self.target = int(data.get("target_samples") or wt.TARGET_SAMPLES)
        self.min_ok = int(data.get("min_samples") or wt.MIN_SAMPLES)
        self._session_ok = 0

        head = ctk.CTkFrame(self, fg_color=theme.BG_DEEP, height=56, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        ctk.CTkLabel(
            head, text="ENTRAÎNER LE PRÉNOM", font=mono(15, True), text_color=theme.TEXT_PRIMARY,
        ).pack(side="left", padx=16, pady=14)
        ctk.CTkFrame(head, fg_color=theme.ACCENT, width=3, corner_radius=0).place(
            x=0, y=0, relheight=1,
        )

        body = ctk.CTkFrame(self, fg_color=theme.BG_MAIN, corner_radius=0)
        body.pack(fill="both", expand=True, padx=18, pady=14)

        nom = NOM_IA or "Nova"
        ctk.CTkLabel(
            body,
            text=f"Dis mon prénom « {nom} » plusieurs fois.\n"
                 f"J'enregistre comment le micro m'entend (toi).",
            font=mono(11), text_color=theme.TEXT_SECONDARY, justify="left",
        ).pack(anchor="w", pady=(0, 12))

        self.progress = ctk.CTkLabel(
            body, text=self._progress_label(), font=mono(18, True), text_color=theme.ACCENT,
        )
        self.progress.pack(anchor="w", pady=(0, 8))

        self.status = ctk.CTkLabel(
            body,
            text="Appuie sur Commencer, puis parle clairement.",
            font=mono(11), text_color=theme.TEXT_MUTED, wraplength=400, justify="left",
        )
        self.status.pack(anchor="w", pady=(0, 16))

        self.aliases_lbl = ctk.CTkLabel(
            body, text=self._aliases_preview(), font=mono(9),
            text_color=theme.TEXT_MUTED, wraplength=400, justify="left",
        )
        self.aliases_lbl.pack(anchor="w", pady=(0, 12))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(8, 0))
        self.btn_go = ctk.CTkButton(
            row, text="Commencer", height=36, corner_radius=8, width=130,
            font=mono(11, True), fg_color=theme.ACCENT_DIM, hover_color=theme.LINE,
            text_color=theme.TEXT_PRIMARY, border_width=1, border_color=theme.ACCENT,
            command=self._commencer,
        )
        self.btn_go.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="Réinitialiser", height=36, corner_radius=8, width=120,
            font=mono(10), fg_color=theme.BG_PANEL, hover_color=theme.ACCENT_DIM,
            text_color=theme.TEXT_SECONDARY, border_width=1, border_color=theme.LINE,
            command=self._reset,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            row, text="Fermer", height=36, corner_radius=8, width=90,
            font=mono(10), fg_color=theme.GLASS2, hover_color=theme.ACCENT_DIM,
            text_color=theme.TEXT_SECONDARY, command=self._fermer,
        ).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self.bind("<Escape>", lambda e: self._fermer())
        self.after(40, self.focus_force)
        self._set_phase("enrolling")

    def _progress_label(self) -> str:
        data = wt.charger()
        n = len(data.get("aliases") or [])
        return f"{min(n, self.target)} / {self.target}"

    def _aliases_preview(self) -> str:
        data = wt.charger()
        als = data.get("aliases") or []
        if not als:
            return "Aucune variante enregistrée."
        apercu = ", ".join(als[:8])
        plus = f" (+{len(als) - 8})" if len(als) > 8 else ""
        return f"Variantes : {apercu}{plus}"

    def _set_phase(self, phase: str | None):
        if self.on_phase:
            try:
                self.on_phase(phase)
            except Exception:
                pass

    def _ui(self, fn):
        try:
            self.after(0, fn)
        except Exception:
            pass

    def _commencer(self):
        if self._busy:
            return
        self._cancel = False
        self._busy = True
        self._set_phase("enrolling")
        self.btn_go.configure(state="disabled", text="Écoute…")
        threading.Thread(target=self._boucle, daemon=True).start()

    def _boucle(self):
        try:
            while not self._cancel:
                data = wt.charger()
                n_alias = len(data.get("aliases") or [])
                if n_alias >= self.target and data.get("enabled"):
                    break

                etape = min(n_alias + 1, self.target)
                prompt = "Dis mon prénom." if n_alias == 0 else "Encore une fois."
                self._ui(lambda p=prompt, e=etape: (
                    self.status.configure(text=f"{p} ({e}/{self.target})"),
                    self.progress.configure(text=f"{e - 1} / {self.target}"),
                ))
                try:
                    self.voice.parler(prompt, attendre=True)
                except Exception:
                    pass
                if self._cancel:
                    break

                try:
                    entendu = AstatVoice.ecouter(timeout=5, phrase_limit=4)
                except Exception:
                    self._ui(lambda: self.status.configure(
                        text="Rien entendu — on réessaie.",
                    ))
                    try:
                        self.voice.parler("Je n'ai pas entendu. Réessaie.", attendre=True)
                    except Exception:
                        pass
                    continue

                ok, err, _ = wt.valider_echantillon(entendu)
                if not ok:
                    self._ui(lambda m=err: self.status.configure(text=m))
                    try:
                        self.voice.parler(err, attendre=True)
                    except Exception:
                        pass
                    continue

                try:
                    data = wt.ajouter_echantillon(entendu, nom_ia=NOM_IA)
                except ValueError as exc:
                    self._ui(lambda m=str(exc): self.status.configure(text=m))
                    continue

                self._session_ok += 1
                n = len(data.get("aliases") or [])
                self._ui(lambda: (
                    self.progress.configure(text=f"{min(n, self.target)} / {self.target}"),
                    self.aliases_lbl.configure(text=self._aliases_preview()),
                    self.status.configure(text=f"Bien reçu : « {entendu} »"),
                ))
                try:
                    if data.get("enabled") and n >= self.target:
                        break
                    self.voice.parler("Parfait.", attendre=True)
                except Exception:
                    pass

            data = wt.charger()
            if data.get("enabled"):
                msg = "Prénom enregistré, je répondrai comme ça."
                self._ui(lambda: self.status.configure(text=msg))
                try:
                    self.voice.parler(msg, attendre=True)
                except Exception:
                    pass
                self._set_phase(None)
                if self.on_done:
                    try:
                        self.after(0, self.on_done)
                    except Exception:
                        pass
            else:
                reste = self.min_ok - len(data.get("aliases") or [])
                if reste > 0:
                    self._ui(lambda r=reste: self.status.configure(
                        text=f"Il m'en faut encore {r}. Relance Commencer.",
                    ))
        finally:
            self._busy = False
            self._ui(lambda: self.btn_go.configure(state="normal", text="Reprendre"))

    def _reset(self):
        if self._busy:
            self._cancel = True
        wt.reinitialiser()
        self._session_ok = 0
        self.progress.configure(text=self._progress_label())
        self.aliases_lbl.configure(text=self._aliases_preview())
        self.status.configure(text="Entraînement effacé. Tu peux recommencer.")

    def _fermer(self):
        self._cancel = True
        self._set_phase(None)
        try:
            self.destroy()
        except Exception:
            pass


def ouvrir_entrainement(master, voice=None, on_done=None, on_phase=None):
    win = WakeEnrollWindow(master, voice=voice, on_done=on_done, on_phase=on_phase)
    try:
        win.lift()
        win.focus_force()
        win.attributes("-topmost", True)
        win.after(400, lambda: win.attributes("-topmost", False))
    except Exception:
        pass
    return win
