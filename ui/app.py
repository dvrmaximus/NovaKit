import datetime
import random
import re
import threading
import time
import tkinter as tk

import customtkinter as ctk

try:
    import speech_recognition as sr
    MICRO_DISPONIBLE = True
except ImportError:
    sr = None
    MICRO_DISPONIBLE = False

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

from brain import AstatBrain
from config import (
    DESKTOP_MODE, DESKTOP_MONITOR, KIT_VERSION, MOT_MAGIQUE, MODELE_GEMINI,
    NOM_IA, NOM_IA_AFFICHE, REMOTE_PIN, REMOTE_PORT, VILLE_DEFAUT, DATA_DIR,
)
from core.hub import AstatHub
from remote.network import obtenir_ip_wifi
from remote import state as remote_state
from ui.hud_canvas import HudCanvas
import ui.hud_theme as theme
from ui.hud_theme import (
    ACCENT, ACCENT_DANGER, ACCENT_DIM, ACCENT_SOFT, ACCENT_WARN, BG_DEEP, BG_INPUT,
    BG_MAIN, BG_PANEL, BG_PANEL2, BUBBLE_ASTAT, BUBBLE_USER, FONT_MONO, FONT_MONO_FALLBACK,
    FONT_UI, GLASS, GLASS2, GLASS_BORDER, GLASS_BORDER_HOT, LINE, MODULES, QUICK_ACTIONS,
    SUCCESS, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY, charger_accent_profil,
)
from ui.hud_widgets import MeterBar, SectionTitle, StatusDot, mono
from ui.win_desktop import (
    HotkeyListener, bring_to_front, ensure_interactive, hwnd_toplevel,
    list_monitors, resolve_monitor, screen_geometry, screen_size,
    send_to_desktop_layer, set_click_through, set_window_alpha,
)
from voice import AstatVoice


class AstatApp:
    def __init__(self, root, desktop_mode: bool = True):
        self.root = root
        self.desktop_mode = desktop_mode
        self.root.title(f"{NOM_IA_AFFICHE} // HUD v{KIT_VERSION}")
        self.click_through = False
        self._hwnd = None
        self._hotkey = None
        self._drag_data = {"x": 0, "y": 0}
        self.cpu_meter = None
        self.ram_meter = None
        self.status_dot = None
        self._boot_overlay = None
        self._boot_sub = None
        self._monitor = resolve_monitor(DESKTOP_MONITOR) if desktop_mode else None

        ctk.set_appearance_mode("dark")
        try:
            charger_accent_profil()
        except Exception:
            pass
        self.hub = AstatHub.get()
        self.hub.init_brain(AstatBrain())
        self.hub.on_message(self._on_hub_message)
        self.voice = AstatVoice()
        self._telemetry_interval = 3500
        self._last_tunnel_sig = None

        self.font_hud = mono(11)
        self.font_hud_b = mono(11, True)
        self.font_title = mono(32, True)
        self.font_brand = mono(42, True)
        self.font_sub = mono(9)
        try:
            self.font_chat = ctk.CTkFont(family=FONT_UI, size=13)
        except Exception:
            self.font_chat = ctk.CTkFont(family="Segoe UI", size=13)
        self.font_clock = mono(36, True)

        self.orb_state = "idle"
        self.listening_active = False
        self.stop_background_listening = None
        self.background_recognizer = sr.Recognizer() if MICRO_DISPONIBLE else None
        self.processing = False
        self.boot_done = False
        # Réveil vocal en 2 temps : sleeping → ack → awaiting_command → sleeping
        # Phase "enrolling" : calibration du prénom (ignore wake/commandes)
        self._voice_phase = "sleeping"  # sleeping | acking | awaiting_command | enrolling
        self._command_deadline = 0.0
        self._wake_token = 0
        self._command_window_s = 8.0
        self._ack_phrases = ("Oui ?", "Je t'écoute.", "Oui, dis-moi.")
        self._wake_tip_shown = False
        self._enroll_paused_listen = False

        if self.desktop_mode:
            self._setup_desktop_window()
            self._construire_desktop_hud()
        else:
            self.root.geometry("1280x800")
            self.root.minsize(1000, 680)
            self.root.configure(fg_color=BG_MAIN)
            self.root.bind("<F11>", self._toggle_fullscreen)
            self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
            self._construire_hud()

        self.root.bind("<Control-k>", lambda e: self.entry.focus())
        self.root.bind("<Control-Shift-A>", lambda e: self._toggle_click_through())
        self.root.bind("<Control-Shift-Q>", lambda e: self._quitter())
        self.root.bind("<F2>", lambda e: self._ouvrir_parametres())
        self.root.bind("<Control-comma>", lambda e: self._ouvrir_parametres())

        self._demarrer_remote()
        self._demarrer_boot()
        self._tick_horloge()
        self._tick_telemetry()
        self.root.after(2500, self._check_backup_quotidienne)

    # ── Mode fond d'écran ─────────────────────────────────────────

    def _setup_desktop_window(self):
        self._monitor = resolve_monitor(DESKTOP_MONITOR)
        self.root.geometry(screen_geometry(self._monitor))
        self.root.overrideredirect(True)
        self.root.configure(fg_color=BG_DEEP)
        try:
            self.root.wm_attributes("-alpha", 0.92)
            self.root.wm_attributes("-topmost", True)
        except Exception:
            pass
        self.root.bind("<Escape>", lambda e: self._toggle_click_through())
        self.root.after(200, self._appliquer_overlay_win32)

    def _appliquer_overlay_win32(self):
        try:
            self.root.update_idletasks()
            # Recolle sur le bon moniteur (Tk peut recentrer sur le primaire)
            if self._monitor:
                self.root.geometry(screen_geometry(self._monitor))
            self._hwnd = hwnd_toplevel(self.root)
            ensure_interactive(self._hwnd, 240)
            set_click_through(self._hwnd, False)
            try:
                self.root.wm_attributes("-topmost", True)
                self.root.wm_attributes("-alpha", 0.94)
                self.root.focus_force()
                self.root.lift()
            except Exception:
                pass
            if self._hotkey:
                try:
                    self._hotkey.unregister()
                except Exception:
                    pass
            self._hotkey = HotkeyListener(
                self.root,
                callback=lambda: self.root.after(0, self._toggle_click_through),
                hwnd=None,  # file de messages du thread (fiable avec pythonw)
            )
            self.root.bind_all("<F8>", lambda e: self._toggle_click_through())
            self.root.bind_all("<KeyPress-F8>", lambda e: self._toggle_click_through())
            self.root.bind_all("<Control-Shift-a>", lambda e: self._toggle_click_through())
            self.root.bind_all("<Control-Shift-A>", lambda e: self._toggle_click_through())
            self.root.after(500, lambda: ensure_interactive(self._hwnd, 240) if self._hwnd else None)
            self.root.after(1500, self._ensure_hotkey_alive)
        except Exception as exc:
            print(f"[desktop] overlay: {exc}")

    def _ensure_hotkey_alive(self):
        """Relance le listener si le polling est mort."""
        if not self.desktop_mode:
            return
        if not self._hotkey or not self._hotkey.registered:
            self._hotkey = HotkeyListener(
                self.root,
                callback=lambda: self.root.after(0, self._toggle_click_through),
            )
        try:
            self.root.after(3000, self._ensure_hotkey_alive)
        except Exception:
            pass

    def _keep_desktop_layer(self):
        return

    def _glass(self, parent, **kw):
        defaults = dict(
            fg_color=GLASS, corner_radius=10,
            border_width=1, border_color=GLASS_BORDER,
        )
        defaults.update(kw)
        return ctk.CTkFrame(parent, **defaults)

    def _btn(self, parent, text, command, primary=False, danger=False, **kw):
        if danger:
            fg, hover, tc = GLASS2, ACCENT_DANGER, TEXT_SECONDARY
        elif primary:
            fg, hover, tc = ACCENT_DIM, LINE, TEXT_PRIMARY
        else:
            fg, hover, tc = GLASS2, ACCENT_DIM, TEXT_SECONDARY
        opts = dict(
            text=text, font=self.font_hud_b if primary else self.font_hud,
            fg_color=fg, hover_color=hover, text_color=tc,
            border_width=1, border_color=LINE,
            corner_radius=8, height=kw.pop("height", 32), command=command,
        )
        opts.update(kw)
        return ctk.CTkButton(parent, **opts)

    def _est_createur(self) -> bool:
        try:
            from online.admin_local import est_createur
            return est_createur()
        except Exception:
            return False

    def _construire_desktop_hud(self):
        mon = self._monitor or resolve_monitor(DESKTOP_MONITOR)
        self._monitor = mon
        sw, sh = mon["width"], mon["height"]
        panel_h = max(360, sh - 140)
        left_w, right_w = 236, 280
        center_w = min(520, max(380, sw - left_w - right_w - 72))
        createur = self._est_createur()

        stage = ctk.CTkFrame(self.root, fg_color=BG_DEEP, corner_radius=0)
        stage.pack(fill="both", expand=True)
        self._stage = stage

        # ── Top bar (fine, sobre) ──
        top = self._glass(stage, width=sw - 40, height=44, corner_radius=10)
        top.place(x=20, y=12)
        top.pack_propagate(False)

        brand_row = ctk.CTkFrame(top, fg_color="transparent")
        brand_row.pack(side="left", padx=14, pady=6)
        self.status_dot = StatusDot(brand_row)
        self.status_dot.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            brand_row, text=NOM_IA_AFFICHE, font=mono(15, True), text_color=TEXT_PRIMARY,
        ).pack(side="left")
        n_mon = len(list_monitors())
        mon_tag = "sec" if not mon.get("primary") else "pri"
        ctk.CTkLabel(
            brand_row,
            text=f"  v{KIT_VERSION}  ·  {mon_tag}",
            font=self.font_sub, text_color=TEXT_MUTED,
        ).pack(side="left", pady=2)

        self.top_status = ctk.CTkLabel(top, text="démarrage…", font=self.font_hud, text_color=TEXT_MUTED)
        self.top_status.pack(side="left", padx=10)
        modele = getattr(self.hub.brain, "modele", MODELE_GEMINI)
        ctk.CTkLabel(top, text=modele, font=self.font_sub, text_color=TEXT_MUTED).pack(side="left", padx=4)

        self._btn(top, "✕", self._quitter, danger=True, width=34, height=28).pack(
            side="right", padx=(4, 12), pady=8
        )
        self._btn(top, "Paramètres", self._ouvrir_parametres, primary=True, width=100, height=28).pack(
            side="right", padx=4, pady=8
        )
        self.desk_mode_btn = self._btn(
            top, "Bureau libre", self._toggle_click_through, width=100, height=28,
        )
        self.desk_mode_btn.pack(side="right", padx=4, pady=8)
        self._btn(top, "Sous apps", self._pin_under_apps, width=80, height=28).pack(
            side="right", padx=4, pady=8
        )
        if n_mon > 1:
            self._btn(top, "Écran", self._cycle_monitor, width=60, height=28).pack(
                side="right", padx=4, pady=8
            )
        ctk.CTkLabel(top, text="F8", font=self.font_sub, text_color=TEXT_MUTED).pack(
            side="right", padx=6
        )

        # ── Left telemetry ──
        left = self._glass(stage, width=left_w, height=panel_h, corner_radius=10)
        left.place(x=20, y=66)
        left.pack_propagate(False)
        self._fill_telemetry_panel(left)

        # ── Right actions (+ admin créateur) ──
        right = self._glass(stage, width=right_w, height=panel_h, corner_radius=10)
        right.place(x=sw - right_w - 20, y=66)
        right.pack_propagate(False)
        self._fill_actions_panel(right, createur=createur)

        # ── Center ──
        cx = sw // 2
        center = ctk.CTkFrame(
            stage, fg_color=BG_DEEP, corner_radius=0,
            width=center_w, height=panel_h,
        )
        center.place(x=cx - center_w // 2, y=66)
        center.pack_propagate(False)

        ctk.CTkLabel(
            center, text=NOM_IA_AFFICHE, font=mono(28, True), text_color=TEXT_PRIMARY,
        ).pack(pady=(10, 0))
        self.status_label = ctk.CTkLabel(
            center, text="démarrage…", font=self.font_hud, text_color=TEXT_MUTED,
        )
        self.status_label.pack(pady=(2, 6))

        self.hud_canvas = HudCanvas(center, size=220, bg=BG_DEEP)
        self.hud_canvas.pack(pady=(0, 2))
        self.hud_canvas.bind("<Double-Button-1>", lambda e: self.start_listening())
        self.hud_canvas.bind("<Button-1>", lambda e: self.entry.focus())

        ctk.CTkLabel(
            center, text="double-clic · parler    clic · commande",
            font=self.font_sub, text_color=TEXT_MUTED,
        ).pack(pady=(2, 6))

        log_frame = self._glass(center, corner_radius=10)
        log_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))
        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(hdr, text="Journal", font=self.font_hud_b, text_color=TEXT_MUTED).pack(side="left")
        self.thinking_label = ctk.CTkLabel(hdr, text="", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.thinking_label.pack(side="right")
        ctk.CTkFrame(log_frame, fg_color=LINE, height=1).pack(fill="x", padx=10)
        self.zone_chat = ctk.CTkScrollableFrame(log_frame, fg_color="transparent")
        self.zone_chat.pack(fill="both", expand=True, padx=6, pady=(4, 8))

        # ── Command bar ──
        barre = self._glass(stage, width=sw - 40, height=56, corner_radius=10)
        barre.place(x=20, y=sh - 70)
        barre.pack_propagate(False)
        inner = ctk.CTkFrame(barre, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=10)
        self.entry = ctk.CTkEntry(
            inner,
            placeholder_text=f"Parler à {NOM_IA}…  (Ctrl+K)",
            fg_color=BG_INPUT, border_color=LINE, border_width=1,
            text_color=TEXT_PRIMARY, font=self.font_chat, height=36, corner_radius=8,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send_text_message)
        self.mic_button = self._btn(
            inner, "Parler", self.start_listening, primary=True, width=84, height=36,
        )
        self.mic_button.pack(side="left")

        # Boot veil
        self._boot_overlay = ctk.CTkFrame(stage, fg_color=BG_DEEP, corner_radius=0)
        self._boot_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        ctk.CTkLabel(
            self._boot_overlay, text=NOM_IA_AFFICHE, font=mono(36, True), text_color=TEXT_PRIMARY,
        ).place(relx=0.5, rely=0.44, anchor="center")
        self._boot_sub = ctk.CTkLabel(
            self._boot_overlay, text="démarrage…", font=self.font_hud, text_color=TEXT_MUTED,
        )
        self._boot_sub.place(relx=0.5, rely=0.52, anchor="center")

    def _fill_telemetry_panel(self, panel):
        pad = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=10, pady=10)

        SectionTitle(pad, "Horloge").pack(fill="x", pady=(0, 2))
        self.clock_label = ctk.CTkLabel(pad, text="--:--:--", font=mono(28, True), text_color=TEXT_PRIMARY)
        self.clock_label.pack(anchor="w")
        self.date_label = ctk.CTkLabel(pad, text="—", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.date_label.pack(anchor="w", pady=(0, 8))

        SectionTitle(pad, "Système").pack(fill="x", pady=(4, 6))
        self.cpu_meter = MeterBar(pad, "CPU")
        self.cpu_meter.pack(fill="x", pady=(0, 8))
        self.ram_meter = MeterBar(pad, "RAM")
        self.ram_meter.pack(fill="x", pady=(0, 4))
        self.cpu_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)
        self.ram_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)

        SectionTitle(pad, "Lieu").pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(
            pad, text=VILLE_DEFAUT, font=self.font_hud_b, text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        SectionTitle(pad, "Modules").pack(fill="x", pady=(10, 4))
        self.module_labels = {}
        self.module_status_labels = {}
        for nom, statut in MODULES:
            row = ctk.CTkFrame(pad, fg_color="transparent")
            row.pack(fill="x", pady=1)
            if nom == "Gmail":
                couleur, etat = TEXT_MUTED, "…"
            elif statut == "online":
                couleur, etat = SUCCESS, "on"
            elif statut == "micro" and MICRO_DISPONIBLE:
                couleur, etat = ACCENT_WARN, "rdy"
            else:
                couleur, etat = TEXT_MUTED, "off"
            etat_lbl = ctk.CTkLabel(row, text=etat, font=self.font_sub, text_color=couleur, width=32)
            etat_lbl.pack(side="left")
            lbl = ctk.CTkLabel(row, text=nom, font=self.font_hud, text_color=TEXT_SECONDARY)
            lbl.pack(side="left")
            self.module_labels[nom] = lbl
            self.module_status_labels[nom] = etat_lbl

        SectionTitle(pad, "Mobile").pack(fill="x", pady=(10, 4))
        ip = obtenir_ip_wifi()
        self.remote_url_wifi = f"http://{ip}:{REMOTE_PORT}"
        self.remote_url = self.remote_url_wifi
        ctk.CTkLabel(pad, text="Wi‑Fi", font=self.font_sub, text_color=TEXT_MUTED).pack(anchor="w")
        self.wifi_label = ctk.CTkLabel(
            pad, text=self.remote_url_wifi, font=self.font_sub, text_color=TEXT_SECONDARY,
            cursor="hand2", wraplength=200, justify="left",
        )
        self.wifi_label.pack(anchor="w")
        self.wifi_label.bind("<Button-1>", lambda e: self._copier_url(self.remote_url_wifi))
        ctk.CTkLabel(pad, text="Internet", font=self.font_sub, text_color=TEXT_MUTED).pack(
            anchor="w", pady=(6, 0)
        )
        self.tunnel_label = ctk.CTkLabel(
            pad, text="Connexion…", font=self.font_sub,
            text_color=ACCENT_WARN, wraplength=200, justify="left",
        )
        self.tunnel_label.pack(anchor="w", pady=(0, 6))
        self._btn(pad, "Copier URL", lambda: self._copier_url(self.remote_url), height=28).pack(
            fill="x", pady=2
        )
        self._btn(pad, "Navigateur", self._ouvrir_url_navigateur, height=28).pack(fill="x", pady=2)
        ctk.CTkLabel(pad, text=f"PIN  {REMOTE_PIN}", font=self.font_hud_b, text_color=TEXT_PRIMARY).pack(
            anchor="w", pady=(8, 0)
        )
        self.remote_clients_label = ctk.CTkLabel(pad, text="Serveur…", font=self.font_sub, text_color=TEXT_MUTED)
        self.remote_clients_label.pack(anchor="w", pady=(2, 0))

    def _fill_actions_panel(self, panel, createur: bool = False):
        pad = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=10, pady=10)

        if createur:
            try:
                from ui.admin_panel import AdminHudPanel
                AdminHudPanel(pad).pack(fill="x", pady=(0, 10))
            except Exception as exc:
                ctk.CTkLabel(
                    pad, text=f"Admin : {exc}", font=self.font_sub, text_color=ACCENT_WARN,
                ).pack(anchor="w", pady=(0, 8))

        SectionTitle(pad, "Actions").pack(fill="x", pady=(0, 6))
        grid = ctk.CTkFrame(pad, fg_color="transparent")
        grid.pack(fill="x")
        for i, (label, cmd) in enumerate(QUICK_ACTIONS):
            btn = ctk.CTkButton(
                grid, text=label, font=self.font_hud,
                fg_color=GLASS2, hover_color=ACCENT_DIM,
                border_color=LINE, border_width=1,
                text_color=TEXT_SECONDARY, height=34, corner_radius=6,
                command=lambda c=cmd: self._action_rapide(c),
            )
            btn.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        SectionTitle(pad, "Contrôles").pack(fill="x", pady=(12, 6))
        self.toggle_button = ctk.CTkButton(
            pad, text=f"Écoute « {MOT_MAGIQUE} »",
            font=self.font_hud, fg_color=GLASS2, hover_color=ACCENT_DIM,
            border_color=LINE, border_width=1, text_color=TEXT_SECONDARY,
            height=36, corner_radius=8, command=self.toggle_background_listening,
        )
        self.toggle_button.pack(fill="x", pady=2)
        self._btn(pad, "Paramètres", self._ouvrir_parametres, primary=True, height=36).pack(
            fill="x", pady=(8, 2)
        )
        self._btn(pad, "Discussion", self._ouvrir_discussion, height=34).pack(fill="x", pady=2)
        self._btn(pad, "Parler", self.start_listening, height=34).pack(fill="x", pady=2)

        tip = ctk.CTkLabel(
            pad,
            text="F8 · bureau libre\nCtrl+, · paramètres",
            font=self.font_sub, text_color=TEXT_MUTED, justify="left",
        )
        tip.pack(anchor="w", pady=(12, 0))

    def _toggle_click_through(self, event=None):
        if not self.desktop_mode:
            return
        if not self._hwnd:
            try:
                self._hwnd = hwnd_toplevel(self.root)
            except Exception:
                return
        self.click_through = not self.click_through
        if self.click_through:
            set_click_through(self._hwnd, True)
            if hasattr(self, "desk_mode_btn"):
                self.desk_mode_btn.configure(text="Reprendre", fg_color=ACCENT_DIM, text_color=TEXT_PRIMARY)
            self.top_status.configure(text="bureau libre · F8")
            try:
                self.root.wm_attributes("-alpha", 0.35)
                self.root.wm_attributes("-topmost", False)
            except Exception:
                pass
            set_window_alpha(self._hwnd, 90)
            send_to_desktop_layer(self._hwnd)
        else:
            set_click_through(self._hwnd, False)
            ensure_interactive(self._hwnd, 240)
            if hasattr(self, "desk_mode_btn"):
                self.desk_mode_btn.configure(text="Bureau libre", fg_color=GLASS2, text_color=TEXT_SECONDARY)
            self.top_status.configure(text="interactif")
            try:
                self.root.wm_attributes("-alpha", 0.94)
                self.root.wm_attributes("-topmost", True)
                self.root.focus_force()
                self.root.lift()
            except Exception:
                pass

    def _cycle_monitor(self):
        """Bascule Astat sur l'autre écran (relance silencieuse)."""
        mons = list_monitors()
        if len(mons) < 2:
            self.ajouter_bulle("astat", "Un seul écran détecté.")
            return
        cur = self._monitor or resolve_monitor(DESKTOP_MONITOR)
        idx = 0
        for i, m in enumerate(mons):
            if m["left"] == cur["left"] and m["top"] == cur["top"]:
                idx = i
                break
        next_idx = (idx + 1) % len(mons)
        pref = str(next_idx + 1)
        try:
            (DATA_DIR / "desktop_monitor.txt").write_text(pref, encoding="utf-8")
        except Exception:
            pass
        self.ajouter_bulle("astat", f"Passage écran {pref}…")
        self.root.after(400, self._relancer_astat)

    def _relancer_astat(self):
        import sys
        from pathlib import Path
        from win_silent import popen_silent
        try:
            if getattr(sys, "frozen", False):
                popen_silent([sys.executable])
            else:
                main = str(Path(__file__).resolve().parent.parent / "main.py")
                exe = Path(sys.executable)
                pw = exe.with_name("pythonw.exe")
                if pw.exists():
                    popen_silent([str(pw), main])
                elif str(exe).lower().endswith("pythonw.exe"):
                    popen_silent([str(exe), main])
                else:
                    popen_silent(["pyw", "-3", main])
        except Exception as exc:
            print(f"[relance] {exc}")
        self._quitter()

    def _ouvrir_discussion(self):
        try:
            from ui.chat_window import ouvrir_discussion
            ouvrir_discussion(self.root)
        except Exception as exc:
            self.ajouter_bulle("astat", f"Discussion impossible : {exc}")

    def _ouvrir_parametres(self, event=None):
        try:
            # HUD desktop : forcer interaction sinon la fenêtre paramètres est invisible/bloquée
            if self.desktop_mode and self.click_through:
                self._toggle_click_through()
            if self._hwnd:
                try:
                    ensure_interactive(self._hwnd, 240)
                    bring_to_front(self._hwnd)
                except Exception:
                    pass
            try:
                self.root.wm_attributes("-topmost", True)
                self.root.focus_force()
            except Exception:
                pass
            from ui.settings_window import ouvrir_parametres
            ouvrir_parametres(
                self.root,
                on_saved=self._apres_parametres,
                on_entrainer=self._ouvrir_entrainement_prenom,
            )
        except Exception as exc:
            self.ajouter_bulle("astat", f"Parametres : {exc}")

    def _ouvrir_entrainement_prenom(self, on_extra=None):
        """Ouvre le flux vocal d'entraînement du prénom."""
        try:
            if self.desktop_mode and self.click_through:
                self._toggle_click_through()
            from ui.wake_enroll import ouvrir_entrainement

            def _done():
                self._apres_entrainement_prenom()
                if on_extra:
                    try:
                        on_extra()
                    except Exception:
                        pass

            ouvrir_entrainement(
                self.root,
                voice=self.voice,
                on_done=_done,
                on_phase=self._set_enroll_phase,
            )
        except Exception as exc:
            self.ajouter_bulle("astat", f"Entraînement : {exc}")

    def _set_enroll_phase(self, phase: str | None):
        if phase == "enrolling":
            self._voice_phase = "enrolling"
            self._wake_token += 1
            # Pause l'écoute fond pour laisser le micro à l'entraînement
            if self.listening_active and self.stop_background_listening:
                try:
                    self.stop_background_listening(wait_for_stop=False)
                except Exception:
                    pass
                self.stop_background_listening = None
                self._enroll_paused_listen = True
        else:
            was_enrolling = self._voice_phase == "enrolling"
            if was_enrolling:
                self._voice_phase = "sleeping"
            if getattr(self, "_enroll_paused_listen", False):
                self._enroll_paused_listen = False
                if self.listening_active:
                    try:
                        if MICRO_DISPONIBLE and self.background_recognizer:
                            mic = sr.Microphone()
                            with mic as source:
                                self.background_recognizer.adjust_for_ambient_noise(
                                    source, duration=0.3
                                )
                            self.stop_background_listening = (
                                self.background_recognizer.listen_in_background(
                                    mic, self.on_background_audio, phrase_time_limit=8
                                )
                            )
                    except Exception as exc:
                        print(f"[wake enroll] reprise écoute : {exc}")
            if self.listening_active and was_enrolling:
                try:
                    self.root.after(
                        0, self.definir_etat, "listening",
                        f"dis « {self._libelle_reveil()} » puis ta demande",
                    )
                except Exception:
                    pass

    def _apres_entrainement_prenom(self):
        self._voice_phase = "sleeping"
        self.ajouter_bulle("astat", "Prénom enregistré, je répondrai comme ça.")
        if self.listening_active:
            self.definir_etat("listening", f"dis « {self._libelle_reveil()} » puis ta demande")

    def _check_backup_quotidienne(self):
        try:
            from core.backup import verifier_sauvegarde_quotidienne, besoin_sauvegarde_du_jour
            if besoin_sauvegarde_du_jour():
                verifier_sauvegarde_quotidienne(async_=True)
                self.ajouter_bulle("astat", "Sauvegarde quotidienne en cours…")
        except Exception as exc:
            print(f"[backup] {exc}")

    def _demarrer_lien_createur(self):
        """Heartbeat + réception des commandes du créateur (message/voix)."""
        try:
            from core.creator_link import demarrer_poll
            demarrer_poll(self._executer_commande_createur)
        except Exception as exc:
            print(f"[creator_link] {exc}")

    def _executer_commande_createur(self, cmd: dict):
        action = (cmd.get("action") or "").lower()
        payload = cmd.get("payload") or {}
        if isinstance(payload, str):
            try:
                import json
                payload = json.loads(payload)
            except Exception:
                payload = {"text": payload}
        texte = (payload.get("text") or "").strip()

        def _ui():
            if action in ("message", "status") and texte:
                self.ajouter_bulle("astat", f"[Créateur] {texte}")
            elif action == "message" and not texte:
                self.ajouter_bulle("astat", "[Créateur] ping reçu.")
            if action == "speak" and texte:
                self.ajouter_bulle("astat", texte)
                try:
                    self.voice.parler(texte, attendre=False)
                except Exception:
                    pass
            if action == "ping":
                self.ajouter_bulle("astat", "Ping créateur OK.")
            if action == "status":
                from config import KIT_VERSION, NOM_IA, VILLE_DEFAUT
                msg = f"{NOM_IA} v{KIT_VERSION} · {VILLE_DEFAUT} · en ligne"
                self.ajouter_bulle("astat", f"[Status] {msg}")

        try:
            self.root.after(0, _ui)
        except Exception:
            pass

    def _apres_parametres(self, relancer: bool = False):
        try:
            import config
            charger_accent_profil()
            self._rafraichir_accent()
            self.ajouter_bulle(
                "astat",
                f"Paramètres OK — IA {config.NOM_IA}, PIN {config.REMOTE_PIN}, ville {config.VILLE_DEFAUT}.",
            )
            if hasattr(self, "toggle_button"):
                self.toggle_button.configure(text=f"Écoute « {config.MOT_MAGIQUE} »")
        except Exception:
            pass
        if relancer:
            self.root.after(400, self._relancer_astat)

    def _rafraichir_accent(self):
        """Applique la couleur IA aux widgets déjà construits (sans relancer)."""
        try:
            accent_dim = theme.ACCENT_DIM
            for attr in ("toggle_button", "mic_button", "desk_mode_btn"):
                btn = getattr(self, attr, None)
                if btn is None:
                    continue
                try:
                    txt = str(btn.cget("text") or "")
                    if "Écoute active" in txt or "Reprendre" in txt:
                        btn.configure(fg_color=accent_dim, text_color=theme.TEXT_PRIMARY)
                    elif attr == "toggle_button":
                        btn.configure(fg_color=accent_dim)
                except Exception:
                    pass
            if getattr(self, "hud_canvas", None):
                try:
                    self.hud_canvas.configure(bg=theme.BG_DEEP)
                except Exception:
                    pass
            if getattr(self, "status_label", None):
                try:
                    # ne force la couleur que si en idle/prêt
                    pass
                except Exception:
                    pass
        except Exception:
            pass

    def _pin_under_apps(self):
        """Garde le HUD visible mais sous les autres fenêtres."""
        if not self._hwnd:
            return
        self.click_through = False
        set_click_through(self._hwnd, False)
        try:
            self.root.wm_attributes("-topmost", False)
            self.root.wm_attributes("-alpha", 0.88)
        except Exception:
            pass
        set_window_alpha(self._hwnd, 220)
        send_to_desktop_layer(self._hwnd)
        self.top_status.configure(text="sous les apps")
        if hasattr(self, "desk_mode_btn"):
            self.desk_mode_btn.configure(text="Bureau libre", fg_color=GLASS2, text_color=TEXT_SECONDARY)

    def _quitter(self):
        if self._hotkey:
            try:
                self._hotkey.unregister()
            except Exception:
                pass
        try:
            self.root.destroy()
        except Exception:
            pass

    # ── Construction fenêtre classique ────────────────────────────

    def _construire_hud(self):
        top = ctk.CTkFrame(self.root, fg_color=BG_DEEP, height=40, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(
            top, text=f"{NOM_IA_AFFICHE}  ·  v{KIT_VERSION}",
            font=self.font_hud_b, text_color=TEXT_PRIMARY,
        ).pack(side="left", padx=16)
        self.top_status = ctk.CTkLabel(top, text="démarrage…", font=self.font_hud, text_color=TEXT_MUTED)
        self.top_status.pack(side="right", padx=16)
        modele = getattr(self.hub.brain, "modele", MODELE_GEMINI)
        ctk.CTkLabel(top, text=modele, font=self.font_sub, text_color=TEXT_MUTED).pack(side="right", padx=8)

        body = ctk.CTkFrame(self.root, fg_color=BG_MAIN, corner_radius=0)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._panel_gauche(body)
        self._panel_centre(body)
        self._panel_droit(body)
        self._barre_commande()

    def _panel_gauche(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_PANEL, width=220, corner_radius=0)
        panel.grid(row=0, column=0, sticky="nsew")
        panel.pack_propagate(False)
        pad = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=8, pady=8)

        SectionTitle(pad, "Horloge").pack(fill="x", pady=(4, 2))
        self.clock_label = ctk.CTkLabel(pad, text="--:--", font=mono(26, True), text_color=TEXT_PRIMARY)
        self.clock_label.pack(anchor="w")
        self.date_label = ctk.CTkLabel(pad, text="—", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.date_label.pack(anchor="w", pady=(0, 8))

        SectionTitle(pad, "Système").pack(fill="x", pady=(4, 4))
        self.cpu_meter = MeterBar(pad, "CPU")
        self.cpu_meter.pack(fill="x", pady=(0, 6))
        self.ram_meter = MeterBar(pad, "RAM")
        self.ram_meter.pack(fill="x", pady=(0, 4))
        self.cpu_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)
        self.ram_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)

        SectionTitle(pad, "Lieu").pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(pad, text=VILLE_DEFAUT, font=self.font_hud, text_color=TEXT_SECONDARY).pack(anchor="w")

        SectionTitle(pad, "Modules").pack(fill="x", pady=(8, 4))
        self.module_labels = {}
        self.module_status_labels = {}
        for nom, statut in MODULES:
            row = ctk.CTkFrame(pad, fg_color="transparent")
            row.pack(fill="x", pady=1)
            if nom == "Gmail":
                couleur, etat = TEXT_MUTED, "…"
            elif statut == "online":
                couleur, etat = SUCCESS, "on"
            elif statut == "micro" and MICRO_DISPONIBLE:
                couleur, etat = ACCENT_WARN, "rdy"
            else:
                couleur, etat = TEXT_MUTED, "off"
            etat_lbl = ctk.CTkLabel(row, text=etat, font=self.font_sub, text_color=couleur, width=32)
            etat_lbl.pack(side="left")
            lbl = ctk.CTkLabel(row, text=nom, font=self.font_hud, text_color=TEXT_SECONDARY)
            lbl.pack(side="left")
            self.module_labels[nom] = lbl
            self.module_status_labels[nom] = etat_lbl

        SectionTitle(pad, "Mobile").pack(fill="x", pady=(8, 4))
        ip = obtenir_ip_wifi()
        self.remote_url_wifi = f"http://{ip}:{REMOTE_PORT}"
        self.remote_url = self.remote_url_wifi
        ctk.CTkLabel(pad, text="Wi‑Fi", font=self.font_sub, text_color=TEXT_MUTED).pack(anchor="w")
        self.wifi_label = ctk.CTkLabel(
            pad, text=self.remote_url_wifi, font=self.font_sub, text_color=TEXT_SECONDARY,
            cursor="hand2", wraplength=180, justify="left",
        )
        self.wifi_label.pack(anchor="w")
        self.wifi_label.bind("<Button-1>", lambda e: self._copier_url(self.remote_url_wifi))
        ctk.CTkLabel(pad, text="Internet", font=self.font_sub, text_color=TEXT_MUTED).pack(
            anchor="w", pady=(6, 0)
        )
        self.tunnel_label = ctk.CTkLabel(
            pad, text="Connexion…", font=self.font_sub,
            text_color=ACCENT_WARN, wraplength=180, justify="left",
        )
        self.tunnel_label.pack(anchor="w", pady=(2, 4))
        self._btn(pad, "Copier URL", lambda: self._copier_url(self.remote_url), height=28).pack(
            fill="x", pady=2
        )
        self._btn(pad, "Navigateur", self._ouvrir_url_navigateur, height=28).pack(fill="x", pady=2)
        ctk.CTkLabel(pad, text=f"PIN  {REMOTE_PIN}", font=self.font_hud_b, text_color=TEXT_PRIMARY).pack(
            anchor="w", pady=(6, 0)
        )
        self.remote_clients_label = ctk.CTkLabel(pad, text="Serveur…", font=self.font_sub, text_color=TEXT_MUTED)
        self.remote_clients_label.pack(anchor="w", pady=(2, 2))

    def _panel_centre(self, parent):
        centre = ctk.CTkFrame(parent, fg_color=BG_MAIN, corner_radius=0)
        centre.grid(row=0, column=1, sticky="nsew")
        centre.grid_rowconfigure(2, weight=1)
        centre.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(centre, text=NOM_IA_AFFICHE, font=mono(28, True), text_color=TEXT_PRIMARY).grid(
            row=0, pady=(16, 0)
        )
        self.status_label = ctk.CTkLabel(centre, text="démarrage…", font=self.font_sub, text_color=TEXT_MUTED)
        self.status_label.grid(row=1, pady=(2, 4))

        self.hud_canvas = HudCanvas(centre, size=200, bg=BG_MAIN)
        self.hud_canvas.grid(row=2, pady=4)
        self.hud_canvas.bind("<Double-Button-1>", lambda e: self.start_listening())

        log_frame = self._glass(centre, corner_radius=10)
        log_frame.grid(row=3, sticky="nsew", padx=20, pady=(8, 12))
        centre.grid_rowconfigure(3, weight=1)

        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(hdr, text="Journal", font=self.font_hud_b, text_color=TEXT_MUTED).pack(side="left")
        self.thinking_label = ctk.CTkLabel(hdr, text="", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.thinking_label.pack(side="right")

        self.zone_chat = ctk.CTkScrollableFrame(log_frame, fg_color="transparent")
        self.zone_chat.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _panel_droit(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_PANEL, width=260, corner_radius=0)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.pack_propagate(False)
        pad = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=8, pady=8)

        if self._est_createur():
            try:
                from ui.admin_panel import AdminHudPanel
                AdminHudPanel(pad).pack(fill="x", pady=(0, 10))
            except Exception as exc:
                ctk.CTkLabel(pad, text=f"Admin : {exc}", font=self.font_sub, text_color=ACCENT_WARN).pack(
                    anchor="w"
                )

        SectionTitle(pad, "Actions").pack(fill="x", pady=(0, 6))
        grid = ctk.CTkFrame(pad, fg_color="transparent")
        grid.pack(fill="x")
        for i, (label, cmd) in enumerate(QUICK_ACTIONS):
            btn = ctk.CTkButton(
                grid, text=label, font=self.font_hud,
                fg_color=GLASS2, hover_color=ACCENT_DIM,
                border_color=LINE, border_width=1,
                text_color=TEXT_SECONDARY, height=32, corner_radius=6,
                command=lambda c=cmd: self._action_rapide(c),
            )
            btn.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="ew")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        SectionTitle(pad, "Contrôles").pack(fill="x", pady=(12, 6))
        self.toggle_button = ctk.CTkButton(
            pad, text=f"Écoute « {MOT_MAGIQUE} »",
            font=self.font_hud, fg_color=GLASS2, hover_color=ACCENT_DIM,
            border_color=LINE, border_width=1, text_color=TEXT_SECONDARY,
            height=34, corner_radius=8, command=self.toggle_background_listening,
        )
        self.toggle_button.pack(fill="x", pady=2)
        self._btn(pad, "Plein écran (F11)", self._toggle_fullscreen, height=30).pack(fill="x", pady=2)
        self._btn(pad, "Paramètres (F2)", self._ouvrir_parametres, primary=True, height=34).pack(
            fill="x", pady=2
        )
        self._btn(pad, "Parler", self.start_listening, height=34).pack(fill="x", pady=(6, 2))

    def _barre_commande(self):
        barre = ctk.CTkFrame(self.root, fg_color=BG_DEEP, height=54, corner_radius=0)
        barre.pack(fill="x", side="bottom")
        barre.pack_propagate(False)

        inner = ctk.CTkFrame(barre, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=8)

        self.entry = ctk.CTkEntry(
            inner, placeholder_text=f"Parler à {NOM_IA}…  (Ctrl+K)",
            fg_color=BG_INPUT, border_color=LINE, border_width=1,
            text_color=TEXT_PRIMARY, font=self.font_chat, height=36, corner_radius=8,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send_text_message)

        self.mic_button = self._btn(inner, "Parler", self.start_listening, primary=True, width=80, height=36)
        self.mic_button.pack(side="left")

    # ── Animations & telemetry ────────────────────────────────────

    def _demarrer_boot(self):
        etapes = [
            "modules…",
            "liaison…",
            "voix…",
            "gmail…",
            "prêt.",
        ]
        self._boot_step(0, etapes)

    def _boot_step(self, i, etapes):
        if i < len(etapes):
            msg = etapes[i]
            self.status_label.configure(text=msg)
            self.top_status.configure(text=f"{int((i + 1) / len(etapes) * 100)} %")
            if self._boot_overlay and self._boot_sub:
                self._boot_sub.configure(text=msg)
            self.root.after(420, lambda: self._boot_step(i + 1, etapes))
        else:
            self.boot_done = True
            self.top_status.configure(
                text="en ligne" if self.desktop_mode else "système prêt"
            )
            self.definir_etat("idle", "en attente")
            self._dismiss_boot_overlay()
            self._verifier_gmail_au_demarrage()
            self.root.after(1500, self._demarrer_lien_createur)
            if self.desktop_mode:
                self.root.after(
                    600,
                    lambda: self.ajouter_bulle(
                        "astat",
                        "Prêt. Double-clic sur le cercle pour parler — F8 pour le bureau.",
                    ),
                )

    def _dismiss_boot_overlay(self):
        ov = self._boot_overlay
        if not ov:
            return
        try:
            ov.destroy()
        except Exception:
            pass
        self._boot_overlay = None

    def _verifier_gmail_au_demarrage(self):
        try:
            from tools.gmail_tools import gmail_est_connecte
            connecte = gmail_est_connecte()
        except Exception:
            connecte = False

        if "Gmail" in self.module_status_labels:
            lbl = self.module_status_labels["Gmail"]
            if connecte:
                lbl.configure(text="on", text_color=SUCCESS)
                self.ajouter_bulle("astat", "Gmail déjà connecté.")
            else:
                lbl.configure(text="off", text_color=ACCENT_WARN)
                self.ajouter_bulle("astat", "Gmail non lié — dis « connecte Gmail » une fois.")

    def _tick_horloge(self):
        try:
            if not self.root.winfo_exists():
                return
            if str(self.root.state()) == "iconic":
                self.root.after(2000, self._tick_horloge)
                return
        except Exception:
            return
        now = datetime.datetime.now()
        txt = now.strftime("%H:%M:%S")
        if getattr(self, "_last_clock", None) != txt:
            self._last_clock = txt
            self.clock_label.configure(text=txt)
        jours = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        mois = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUN", "JUL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"]
        date_txt = f"{jours[now.weekday()]}  ·  {now.day} {mois[now.month - 1]}  ·  {now.year}"
        if getattr(self, "_last_date", None) != date_txt:
            self._last_date = date_txt
            self.date_label.configure(text=date_txt)
        self.root.after(1000, self._tick_horloge)

    def _tick_telemetry(self):
        try:
            if not self.root.winfo_exists():
                return
            if str(self.root.state()) == "iconic":
                self.root.after(5000, self._tick_telemetry)
                return
        except Exception:
            return
        if PSUTIL_OK:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            if self.cpu_meter:
                self.cpu_meter.set_value(cpu)
            if self.ram_meter:
                self.ram_meter.set_value(ram)
        elif self.cpu_meter:
            self.cpu_meter.set_value(0)
            if self.ram_meter:
                self.ram_meter.set_value(0)
        n = self.hub.remote_clients
        clients_txt = f"{n} tél. lié(s)" if n else "aucun tél. lié"
        clients_col = SUCCESS if n else TEXT_MUTED
        if getattr(self, "_last_clients", None) != (clients_txt, clients_col):
            self._last_clients = (clients_txt, clients_col)
            self.remote_clients_label.configure(text=clients_txt, text_color=clients_col)
        self._maj_tunnel_ui()
        # Ralentir un peu si idle (moins de charge UI)
        interval = 2500 if self.orb_state != "idle" else getattr(self, "_telemetry_interval", 3500)
        self.root.after(interval, self._tick_telemetry)

    def _maj_tunnel_ui(self):
        sig = (
            remote_state.public_url,
            remote_state.tunnel_erreur,
            remote_state.local_url,
        )
        if sig == getattr(self, "_last_tunnel_sig", object()):
            return
        self._last_tunnel_sig = sig
        if remote_state.public_url:
            self.remote_url = remote_state.public_url
            self.tunnel_label.configure(text=remote_state.public_url, text_color=SUCCESS)
        elif remote_state.tunnel_erreur:
            self.tunnel_label.configure(
                text=remote_state.tunnel_erreur[:120], text_color=ACCENT_WARN,
            )
        if remote_state.local_url:
            self.remote_url_wifi = remote_state.local_url
            self.wifi_label.configure(text=remote_state.local_url)

    def _demarrer_remote(self):
        try:
            from remote.startup import demarrer_remote_complet

            def _on_pret(url):
                self.root.after(0, self._maj_tunnel_ui)
                self.root.after(0, lambda: self._url_pret(url))

            def _on_err(msg):
                detail = msg
                if remote_state.serveur_erreur:
                    detail += "\nVoir data/serveur.log"
                self.root.after(0, self._maj_tunnel_ui)
                self.root.after(0, lambda: self.ajouter_bulle("astat", f"Mobile indisponible : {detail}"))

            threading.Thread(
                target=demarrer_remote_complet,
                kwargs={"on_pret": _on_pret, "on_erreur": _on_err},
                daemon=True,
            ).start()
        except ImportError:
            self.wifi_label.configure(text="Remote OFF", text_color=ACCENT_WARN)
            self.tunnel_label.configure(text="pip install fastapi uvicorn", text_color=ACCENT_WARN)
        except Exception as exc:
            self.remote_clients_label.configure(text=f"Remote: {exc}", text_color=ACCENT_WARN)

    def _url_pret(self, url):
        provider = remote_state.tunnel_provider or "internet"
        self.ajouter_bulle(
            "astat",
            f"Contrôle mobile prêt ({provider}).\n{url}\nPIN : {REMOTE_PIN}\n"
            "Sur le téléphone → onglet ÉCRAN pour voir le PC.",
        )

    def _copier_url(self, url=None):
        try:
            import pyperclip
            pyperclip.copy(url or self.remote_url)
            self.status_label.configure(text="URL copiée !")
        except Exception:
            pass

    def _ouvrir_url_navigateur(self):
        import webbrowser
        url = self.remote_url or self.remote_url_wifi
        if url:
            webbrowser.open(url)

    def _on_hub_message(self, role, texte, source):
        expediteur = "astat" if role == "astat" else "toi"
        prefix = "📱 " if source == "mobile" else ""
        self.root.after(0, self.ajouter_bulle, expediteur, prefix + texte)
        if role == "astat" and source == "mobile":
            threading.Thread(target=self._parler_safe, args=(texte,), daemon=True).start()

    def _parler_safe(self, texte):
        self.root.after(0, self.definir_etat, "speaking", "transmission vocale...")
        self.voice.parler(texte, attendre=False)
        etat = "listening" if self.listening_active else "idle"
        statut = (
            f"dis « {self._libelle_reveil()} » puis ta demande"
            if self.listening_active else "en attente de vos ordres"
        )
        self.root.after(0, self.definir_etat, etat, statut)

    def _toggle_fullscreen(self, event=None):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def definir_etat(self, etat, texte_statut=None):
        self.orb_state = etat
        self.hud_canvas.set_state(etat)
        if texte_statut is not None:
            self.status_label.configure(text=texte_statut)

    # ── Chat ──────────────────────────────────────────────────────

    def ajouter_bulle(self, expediteur, texte):
        est_astat = expediteur == "astat"
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        tag = NOM_IA_AFFICHE if est_astat else "VOUS"
        couleur_tag = theme.ACCENT if est_astat else TEXT_MUTED

        conteneur = ctk.CTkFrame(self.zone_chat, fg_color="transparent")
        conteneur.pack(fill="x", pady=6, padx=2)

        header = ctk.CTkFrame(conteneur, fg_color="transparent")
        header.pack(fill="x", anchor="w" if est_astat else "e")
        ctk.CTkLabel(
            header, text=f"▸ {tag}", font=self.font_sub, text_color=couleur_tag,
        ).pack(side="left" if est_astat else "right")
        ctk.CTkLabel(
            header, text=ts, font=self.font_sub, text_color=TEXT_MUTED,
        ).pack(side="left" if est_astat else "right", padx=8)

        bubble = ctk.CTkFrame(
            conteneur,
            fg_color=BUBBLE_ASTAT if est_astat else BUBBLE_USER,
            corner_radius=12,
            border_width=1,
            border_color=GLASS_BORDER if est_astat else LINE,
        )
        bubble.pack(anchor="w" if est_astat else "e", fill="x", pady=(2, 0))
        ctk.CTkLabel(
            bubble, text=texte, font=self.font_chat, text_color=TEXT_PRIMARY,
            justify="left", wraplength=460, anchor="w",
        ).pack(padx=12, pady=10, anchor="w")

        self.root.after(50, lambda: self.zone_chat._parent_canvas.yview_moveto(1.0))

    def _action_rapide(self, commande):
        if not self.boot_done or self.processing:
            return
        threading.Thread(target=self.process_message, args=(commande, "local"), daemon=True).start()

    def send_text_message(self, event=None):
        message = self.entry.get().strip()
        if not message or not self.boot_done or self.processing:
            return
        self.entry.delete(0, "end")
        threading.Thread(target=self.process_message, args=(message, "local"), daemon=True).start()

    # ── Voix ──────────────────────────────────────────────────────

    def start_listening(self):
        if not self.boot_done or self.processing:
            return
        if not MICRO_DISPONIBLE:
            self.ajouter_bulle("astat", "Micro indisponible — pip install pyaudio")
            return
        self.mic_button.configure(state="disabled")
        self.definir_etat("listening", "écoute en cours...")
        threading.Thread(target=self._ecouter_micro, daemon=True).start()

    def _ecouter_micro(self):
        try:
            texte = AstatVoice.ecouter()
            threading.Thread(target=self.process_message, args=(texte, "local"), daemon=True).start()
        except sr.WaitTimeoutError:
            self.root.after(0, self.ajouter_bulle, "astat", "Je n'ai rien entendu.")
        except sr.UnknownValueError:
            self.root.after(0, self.ajouter_bulle, "astat", "Je n'ai pas compris.")
        except Exception as erreur:
            self.root.after(0, self.ajouter_bulle, "astat", f"Erreur micro : {erreur}")
        finally:
            self.root.after(0, lambda: self.mic_button.configure(state="normal"))
            if not self.processing:
                etat = "listening" if self.listening_active else "idle"
                txt = (
                    f"dis « {self._libelle_reveil()} » puis ta demande"
                    if self.listening_active else "en attente de vos ordres"
                )
                self.root.after(0, self.definir_etat, etat, txt)

    def toggle_background_listening(self):
        if not MICRO_DISPONIBLE:
            self.ajouter_bulle("astat", "Micro indisponible — pip install pyaudio")
            return
        if not self.listening_active:
            mic = sr.Microphone()
            with mic as source:
                self.background_recognizer.adjust_for_ambient_noise(source, duration=0.4)
            self.stop_background_listening = self.background_recognizer.listen_in_background(
                mic, self.on_background_audio, phrase_time_limit=8
            )
            self.listening_active = True
            self._voice_phase = "sleeping"
            self._wake_token += 1
            self.toggle_button.configure(text="Écoute active", fg_color=ACCENT_DIM, text_color=TEXT_PRIMARY)
            self.definir_etat("listening", f"dis « {self._libelle_reveil()} » puis ta demande")
            self._proposer_entrainement_si_besoin()
        else:
            if self.stop_background_listening:
                self.stop_background_listening(wait_for_stop=False)
            self.listening_active = False
            self._voice_phase = "sleeping"
            self._wake_token += 1
            self.toggle_button.configure(
                text=f"Écoute « {self._libelle_reveil()} »", fg_color=GLASS2, text_color=TEXT_SECONDARY,
            )
            self.definir_etat("idle", "en attente")

    def _libelle_reveil(self) -> str:
        mots = self._mots_reveil()
        return mots[0] if mots else MOT_MAGIQUE

    def _mots_reveil(self) -> list[str]:
        """Mots d'activation : mot_magique + nom_ia (profil courant)."""
        try:
            import config
            candidats = (
                getattr(config, "MOT_MAGIQUE", "") or "",
                getattr(config, "NOM_IA", "") or "",
            )
        except Exception:
            candidats = (MOT_MAGIQUE or "", NOM_IA or "")
        mots: list[str] = []
        for m in candidats:
            m = str(m).strip().lower()
            if m and m not in mots:
                mots.append(m)
        return mots

    def _trouver_reveil(self, texte: str):
        """Retourne (index, longueur) du premier mot de réveil, ou None.

        Utilise le nom officiel, des variantes STT auto, et les aliases
        enregistrés pendant l'entraînement du prénom (fuzzy).
        """
        try:
            from core.wake_training import trouver_reveil
            return trouver_reveil(texte, noms_officiels=self._mots_reveil())
        except Exception:
            pass
        bas = (texte or "").lower()
        if not bas:
            return None
        meilleur = None
        for mot in self._mots_reveil():
            for match in re.finditer(rf"(?<!\w){re.escape(mot)}(?!\w)", bas):
                pos = (match.start(), match.end() - match.start())
                if meilleur is None or pos[0] < meilleur[0]:
                    meilleur = pos
                break
            if meilleur is None and mot in bas:
                meilleur = (bas.index(mot), len(mot))
        return meilleur

    def _proposer_entrainement_si_besoin(self):
        """Une seule fois : suggère d'entraîner le prénom si pas encore fait."""
        if self._wake_tip_shown:
            return
        try:
            from core.wake_training import est_entraine
            if est_entraine():
                return
        except Exception:
            return
        self._wake_tip_shown = True
        nom = self._libelle_reveil()
        self.ajouter_bulle(
            "astat",
            f"Astuce : dans Paramètres → Voix, « Entraîner mon prénom » "
            f"pour que je reconnaisse mieux ta façon de dire « {nom} ».",
        )

    def _audio_a_ignorer(self) -> bool:
        """Évite le double-déclenchement (TTS / ack / traitement / entraînement)."""
        if self._voice_phase in ("acking", "enrolling") or self.processing:
            return True
        try:
            return bool(self.voice.est_occupe)
        except Exception:
            return bool(getattr(self.voice, "_busy", False))

    def _revenir_sommeil(self, statut: str | None = None):
        self._voice_phase = "sleeping"
        self._wake_token += 1
        if not self.listening_active:
            return
        txt = statut or f"dis « {self._libelle_reveil()} » puis ta demande"
        try:
            self.root.after(0, self.definir_etat, "listening", txt)
        except Exception:
            pass

    def _armer_fenetre_commande(self):
        self._voice_phase = "awaiting_command"
        self._command_deadline = time.monotonic() + self._command_window_s
        token = self._wake_token
        try:
            self.root.after(0, self.definir_etat, "listening", "je t'écoute — parle…")
        except Exception:
            pass

        def _expirer():
            if token != self._wake_token:
                return
            if self._voice_phase != "awaiting_command":
                return
            if time.monotonic() < self._command_deadline:
                return
            self._revenir_sommeil()

        threading.Timer(self._command_window_s + 0.05, _expirer).start()

    def _accuser_puis_ecouter(self):
        """Phase 2 : ack vocal court, puis fenêtre de commande."""
        self._voice_phase = "acking"
        self._wake_token += 1
        token = self._wake_token
        phrase = random.choice(self._ack_phrases)

        def _run():
            try:
                AstatVoice.bip_activation()
                try:
                    self.root.after(0, self.ajouter_bulle, "astat", phrase)
                    self.root.after(0, self.definir_etat, "speaking", phrase)
                except Exception:
                    pass
                self.voice.parler(phrase, attendre=True)
                time.sleep(0.2)  # laisse l'écho TTS retomber
                if token != self._wake_token or not self.listening_active:
                    return
                self._armer_fenetre_commande()
            except Exception:
                self._revenir_sommeil()

        threading.Thread(target=_run, daemon=True).start()

    def on_background_audio(self, recognizer, audio):
        if not self.listening_active or self._audio_a_ignorer():
            return
        try:
            texte = recognizer.recognize_google(audio, language="fr-FR")
        except (sr.UnknownValueError, sr.RequestError):
            return
        texte = (texte or "").strip()
        if not texte:
            return

        # Phase commande : la prochaine phrase est l'ordre (sans mot magique requis)
        if self._voice_phase == "awaiting_command":
            if time.monotonic() <= self._command_deadline:
                reveil = self._trouver_reveil(texte)
                if reveil is not None:
                    apres = texte[reveil[0] + reveil[1]:].strip(" ,.!?;:")
                    if not apres:
                        self._accuser_puis_ecouter()
                        return
                    texte = apres
                self._wake_token += 1  # annule le timer de timeout
                self._voice_phase = "sleeping"
                threading.Thread(
                    target=self.process_message, args=(texte, "local"), daemon=True
                ).start()
                return
            self._revenir_sommeil()
            # hors délai → retombe en détection réveil ci-dessous

        if self._voice_phase != "sleeping":
            return

        reveil = self._trouver_reveil(texte)
        if reveil is None:
            return

        commande = texte[reveil[0] + reveil[1]:].strip(" ,.!?;:")
        # Bonus one-shot : « Astat ouvre YouTube » dans la même phrase
        if commande and len(commande) >= 2:
            AstatVoice.bip_activation()
            threading.Thread(
                target=self.process_message, args=(commande, "local"), daemon=True
            ).start()
            return

        # Flux principal : réveil → ack → écoute de la demande
        self._accuser_puis_ecouter()

    # ── Traitement ────────────────────────────────────────────────

    def _animer_pensee(self, step=0):
        if not self.processing:
            self.thinking_label.configure(text="")
            return
        dots = "." * (step % 4)
        self.thinking_label.configure(text=f"analyse{dots}")
        self.root.after(350, lambda: self._animer_pensee(step + 1))

    def process_message(self, message, source="local"):
        self.processing = True
        self.root.after(0, self.definir_etat, "thinking", "traitement en cours...")
        self.root.after(0, self._animer_pensee)

        try:
            texte = self.hub.process(message, source=source)
        except Exception as exc:
            texte = f"Erreur : {exc}"

        self.processing = False
        self.root.after(0, lambda: self.thinking_label.configure(text=""))

        if source == "local":
            self.root.after(0, self.definir_etat, "speaking", f"{NOM_IA} parle...")
            # Voix en arrière-plan : le texte est déjà affiché, on ne bloque plus
            self.voice.parler(texte, attendre=False)
            if self.listening_active:
                self._voice_phase = "sleeping"
            etat = "listening" if self.listening_active else "idle"
            statut = (
                f"dis « {self._libelle_reveil()} » puis ta demande"
                if self.listening_active else "en attente de vos ordres"
            )
            self.root.after(400, self.definir_etat, etat, statut)


def lancer():
    root = ctk.CTk()
    AstatApp(root, desktop_mode=DESKTOP_MODE)
    root.mainloop()
