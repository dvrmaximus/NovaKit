import datetime
import threading
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
from ui.hud_theme import (
    ACCENT, ACCENT_DANGER, ACCENT_DIM, ACCENT_SOFT, ACCENT_WARN, BG_DEEP, BG_INPUT,
    BG_MAIN, BG_PANEL, BG_PANEL2, BUBBLE_ASTAT, BUBBLE_USER, FONT_MONO, FONT_MONO_FALLBACK,
    FONT_UI, GLASS, GLASS2, GLASS_BORDER, GLASS_BORDER_HOT, LINE, MODULES, QUICK_ACTIONS,
    SUCCESS, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
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
        self.hub = AstatHub.get()
        self.hub.init_brain(AstatBrain())
        self.hub.on_message(self._on_hub_message)
        self.voice = AstatVoice()

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

        self._demarrer_remote()
        self._demarrer_boot()
        self._tick_horloge()
        self._tick_telemetry()

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
            fg_color=GLASS, corner_radius=14,
            border_width=1, border_color=GLASS_BORDER,
        )
        defaults.update(kw)
        return ctk.CTkFrame(parent, **defaults)

    def _btn(self, parent, text, command, primary=False, danger=False, **kw):
        if danger:
            fg, hover, tc = GLASS2, ACCENT_DANGER, TEXT_SECONDARY
        elif primary:
            fg, hover, tc = ACCENT_DIM, ACCENT, BG_DEEP
        else:
            fg, hover, tc = GLASS2, ACCENT_DIM, ACCENT_SOFT
        opts = dict(
            text=text, font=self.font_hud_b if primary else self.font_hud,
            fg_color=fg, hover_color=hover, text_color=tc,
            border_width=1, border_color=GLASS_BORDER_HOT if primary else LINE,
            corner_radius=8, height=kw.pop("height", 32), command=command,
        )
        opts.update(kw)
        return ctk.CTkButton(parent, **opts)

    def _construire_desktop_hud(self):
        mon = self._monitor or resolve_monitor(DESKTOP_MONITOR)
        self._monitor = mon
        sw, sh = mon["width"], mon["height"]
        panel_h = max(360, sh - 150)
        left_w, right_w = 248, 268
        center_w = min(560, max(400, sw - left_w - right_w - 80))

        stage = ctk.CTkFrame(self.root, fg_color=BG_DEEP, corner_radius=0)
        stage.pack(fill="both", expand=True)
        self._stage = stage

        # ── Top bar ──
        top = self._glass(stage, width=sw - 40, height=48, corner_radius=12)
        top.place(x=20, y=14)
        top.pack_propagate(False)

        left_top = ctk.CTkFrame(top, fg_color="transparent")
        left_top.pack(side="left", padx=14, pady=8)
        brand_row = ctk.CTkFrame(left_top, fg_color="transparent")
        brand_row.pack(anchor="w")
        self.status_dot = StatusDot(brand_row)
        self.status_dot.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(
            brand_row, text=NOM_IA_AFFICHE, font=mono(16, True), text_color=ACCENT,
        ).pack(side="left")
        n_mon = len(list_monitors())
        mon_tag = "SEC" if not mon.get("primary") else "PRI"
        ctk.CTkLabel(
            brand_row,
            text=f"  NEURAL HUD  v{KIT_VERSION}  ·  ÉCRAN {mon_tag}",
            font=self.font_sub, text_color=TEXT_MUTED,
        ).pack(side="left", pady=2)

        self.top_status = ctk.CTkLabel(top, text="BOOT SEQUENCE…", font=self.font_hud, text_color=TEXT_MUTED)
        self.top_status.pack(side="left", padx=8)
        modele = getattr(self.hub.brain, "modele", MODELE_GEMINI)
        ctk.CTkLabel(top, text=modele, font=self.font_sub, text_color=TEXT_MUTED).pack(side="left", padx=6)

        self._btn(top, "✕", self._quitter, danger=True, width=36, height=30).pack(
            side="right", padx=(4, 12), pady=9
        )
        self.desk_mode_btn = self._btn(
            top, "BUREAU LIBRE", self._toggle_click_through, width=120, height=30,
        )
        self.desk_mode_btn.pack(side="right", padx=4, pady=9)
        self._btn(top, "SOUS APPS", self._pin_under_apps, width=100, height=30).pack(
            side="right", padx=4, pady=9
        )
        if n_mon > 1:
            self._btn(top, "ÉCRAN", self._cycle_monitor, width=70, height=30).pack(
                side="right", padx=4, pady=9
            )
        ctk.CTkLabel(top, text="F8", font=self.font_sub, text_color=TEXT_MUTED).pack(
            side="right", padx=8
        )

        # ── Left telemetry ──
        left = self._glass(stage, width=left_w, height=panel_h)
        left.place(x=20, y=74)
        left.pack_propagate(False)
        self._fill_telemetry_panel(left)

        # ── Right actions ──
        right = self._glass(stage, width=right_w, height=panel_h)
        right.place(x=sw - right_w - 20, y=74)
        right.pack_propagate(False)
        self._fill_actions_panel(right)

        # ── Center core ──
        cx = sw // 2
        center = ctk.CTkFrame(
            stage, fg_color=BG_DEEP, corner_radius=0,
            width=center_w, height=panel_h,
        )
        center.place(x=cx - center_w // 2, y=74)
        center.pack_propagate(False)

        ctk.CTkLabel(center, text="  ".join(NOM_IA_AFFICHE), font=self.font_brand, text_color=ACCENT).pack(pady=(6, 0))
        ctk.CTkLabel(
            center, text="— INTERFACE NEURALE —", font=self.font_sub, text_color=TEXT_MUTED,
        ).pack()
        self.status_label = ctk.CTkLabel(
            center, text="initialisation des systèmes…", font=self.font_hud, text_color=ACCENT_SOFT,
        )
        self.status_label.pack(pady=(4, 8))

        orb_wrap = self._glass(center, width=276, height=276, corner_radius=138, border_color=GLASS_BORDER_HOT)
        orb_wrap.pack()
        orb_wrap.pack_propagate(False)
        self.hud_canvas = HudCanvas(orb_wrap, size=260, bg=GLASS)
        self.hud_canvas.pack(expand=True, padx=8, pady=8)
        self.hud_canvas.bind("<Double-Button-1>", lambda e: self.start_listening())
        self.hud_canvas.bind("<Button-1>", lambda e: self.entry.focus())

        hint = ctk.CTkLabel(
            center, text="double-clic noyau · parler   ·   clic · focus commande",
            font=self.font_sub, text_color=TEXT_MUTED,
        )
        hint.pack(pady=(6, 4))

        log_frame = self._glass(center, corner_radius=12, border_color=GLASS_BORDER)
        log_frame.pack(fill="both", expand=True, padx=2, pady=(4, 2))
        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(hdr, text="MISSION LOG", font=self.font_hud_b, text_color=ACCENT_SOFT).pack(side="left")
        self.thinking_label = ctk.CTkLabel(hdr, text="", font=self.font_hud, text_color=ACCENT)
        self.thinking_label.pack(side="right")
        ctk.CTkFrame(log_frame, fg_color=LINE, height=1).pack(fill="x", padx=12)
        self.zone_chat = ctk.CTkScrollableFrame(log_frame, fg_color="transparent")
        self.zone_chat.pack(fill="both", expand=True, padx=8, pady=(4, 10))

        # ── Command bar ──
        barre = self._glass(stage, width=sw - 40, height=64, corner_radius=14, border_color=GLASS_BORDER_HOT)
        barre.place(x=20, y=sh - 78)
        barre.pack_propagate(False)
        inner = ctk.CTkFrame(barre, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)
        ctk.CTkLabel(inner, text="▸ CMD", font=self.font_hud_b, text_color=ACCENT).pack(side="left", padx=(0, 10))
        self.entry = ctk.CTkEntry(
            inner,
            placeholder_text=f"Ordre pour {NOM_IA}…  (Ctrl+K)",
            fg_color=BG_INPUT, border_color=ACCENT_DIM, border_width=1,
            text_color=TEXT_PRIMARY, font=self.font_chat, height=40, corner_radius=10,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.bind("<Return>", self.send_text_message)
        self.mic_button = self._btn(
            inner, "PARLER", self.start_listening, primary=True, width=90, height=40,
        )
        self.mic_button.pack(side="left")

        # Boot veil
        self._boot_overlay = ctk.CTkFrame(stage, fg_color=BG_DEEP, corner_radius=0)
        self._boot_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        boot_lbl = ctk.CTkLabel(
            self._boot_overlay, text=NOM_IA_AFFICHE, font=self.font_brand, text_color=ACCENT,
        )
        boot_lbl.place(relx=0.5, rely=0.42, anchor="center")
        self._boot_sub = ctk.CTkLabel(
            self._boot_overlay, text="INITIALISATION…", font=self.font_hud, text_color=TEXT_MUTED,
        )
        self._boot_sub.place(relx=0.5, rely=0.50, anchor="center")

    def _fill_telemetry_panel(self, panel):
        pad = ctk.CTkFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=12, pady=12)

        SectionTitle(pad, "Horloge").pack(fill="x", pady=(0, 4))
        self.clock_label = ctk.CTkLabel(pad, text="--:--:--", font=self.font_clock, text_color=ACCENT)
        self.clock_label.pack(anchor="w")
        self.date_label = ctk.CTkLabel(pad, text="—", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.date_label.pack(anchor="w", pady=(0, 10))

        SectionTitle(pad, "Système").pack(fill="x", pady=(4, 6))
        self.cpu_meter = MeterBar(pad, "CPU")
        self.cpu_meter.pack(fill="x", pady=(0, 8))
        self.ram_meter = MeterBar(pad, "RAM")
        self.ram_meter.pack(fill="x", pady=(0, 4))
        self.cpu_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)
        self.ram_label = ctk.CTkLabel(pad, text="", font=self.font_sub, text_color=TEXT_MUTED)

        SectionTitle(pad, "Localisation").pack(fill="x", pady=(10, 4))
        ctk.CTkLabel(
            pad, text=VILLE_DEFAUT.upper(), font=self.font_hud_b, text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        SectionTitle(pad, "Modules").pack(fill="x", pady=(10, 4))
        self.module_labels = {}
        self.module_status_labels = {}
        for nom, statut in MODULES:
            row = ctk.CTkFrame(pad, fg_color="transparent")
            row.pack(fill="x", pady=2)
            if nom == "Gmail":
                couleur, etat = TEXT_MUTED, "…"
            elif statut == "online":
                couleur, etat = SUCCESS, "ON"
            elif statut == "micro" and MICRO_DISPONIBLE:
                couleur, etat = ACCENT_WARN, "RDY"
            else:
                couleur, etat = TEXT_MUTED, "OFF"
            etat_lbl = ctk.CTkLabel(row, text=etat, font=self.font_sub, text_color=couleur, width=36)
            etat_lbl.pack(side="left")
            lbl = ctk.CTkLabel(row, text=nom, font=self.font_hud, text_color=TEXT_SECONDARY)
            lbl.pack(side="left")
            self.module_labels[nom] = lbl
            self.module_status_labels[nom] = etat_lbl

        SectionTitle(pad, "Mobile").pack(fill="x", pady=(10, 4))
        ip = obtenir_ip_wifi()
        self.remote_url_wifi = f"http://{ip}:{REMOTE_PORT}"
        self.remote_url = self.remote_url_wifi
        ctk.CTkLabel(pad, text="WIFI", font=self.font_sub, text_color=TEXT_MUTED).pack(anchor="w")
        self.wifi_label = ctk.CTkLabel(
            pad, text=self.remote_url_wifi, font=self.font_sub, text_color=ACCENT_SOFT,
            cursor="hand2", wraplength=210, justify="left",
        )
        self.wifi_label.pack(anchor="w")
        self.wifi_label.bind("<Button-1>", lambda e: self._copier_url(self.remote_url_wifi))
        ctk.CTkLabel(pad, text="INTERNET", font=self.font_sub, text_color=TEXT_MUTED).pack(
            anchor="w", pady=(6, 0)
        )
        self.tunnel_label = ctk.CTkLabel(
            pad, text="Connexion…", font=self.font_sub,
            text_color=ACCENT_WARN, wraplength=210, justify="left",
        )
        self.tunnel_label.pack(anchor="w", pady=(0, 6))
        self._btn(pad, "COPIER URL", lambda: self._copier_url(self.remote_url), primary=True, height=30).pack(
            fill="x", pady=2
        )
        self._btn(pad, "NAVIGATEUR", self._ouvrir_url_navigateur, height=28).pack(fill="x", pady=2)
        ctk.CTkLabel(pad, text=f"PIN  {REMOTE_PIN}", font=self.font_hud_b, text_color=ACCENT).pack(
            anchor="w", pady=(8, 0)
        )
        self.remote_clients_label = ctk.CTkLabel(pad, text="Serveur…", font=self.font_sub, text_color=TEXT_MUTED)
        self.remote_clients_label.pack(anchor="w", pady=(2, 0))

    def _fill_actions_panel(self, panel):
        pad = ctk.CTkFrame(panel, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=12, pady=12)

        SectionTitle(pad, "Actions rapides").pack(fill="x", pady=(0, 8))
        grid = ctk.CTkFrame(pad, fg_color="transparent")
        grid.pack(fill="x")
        for i, (label, cmd) in enumerate(QUICK_ACTIONS):
            btn = ctk.CTkButton(
                grid, text=label, font=self.font_hud_b,
                fg_color=GLASS2, hover_color=ACCENT_DIM,
                border_color=LINE, border_width=1,
                text_color=TEXT_PRIMARY, height=38, corner_radius=8,
                command=lambda c=cmd: self._action_rapide(c),
            )
            btn.grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        SectionTitle(pad, "Protocoles").pack(fill="x", pady=(14, 8))
        self.toggle_button = ctk.CTkButton(
            pad, text=f"ÉCOUTE  « {MOT_MAGIQUE.upper()} »",
            font=self.font_hud_b, fg_color=GLASS2, hover_color=ACCENT_DIM,
            border_color=ACCENT_DIM, border_width=1, text_color=ACCENT_SOFT,
            height=40, corner_radius=8, command=self.toggle_background_listening,
        )
        self.toggle_button.pack(fill="x", pady=3)
        self._btn(pad, "DISCUSSION AVEC L'IA", self._ouvrir_discussion, primary=True, height=44).pack(
            fill="x", pady=(8, 4)
        )
        self._btn(pad, "ACTIVATION VOCALE", self.start_listening, primary=False, height=40).pack(
            fill="x", pady=(4, 4)
        )

        tip = self._glass(pad, corner_radius=10)
        tip.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(
            tip,
            text="HUD plein écran\nF8  →  bureau libre\n✕  →  quitter",
            font=self.font_sub, text_color=TEXT_MUTED, justify="left",
        ).pack(anchor="w", padx=12, pady=10)

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
                self.desk_mode_btn.configure(text="REPRENDRE", fg_color=ACCENT_DIM, text_color=BG_DEEP)
            self.top_status.configure(text="BUREAU LIBRE · F8")
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
                self.desk_mode_btn.configure(text="BUREAU LIBRE", fg_color=GLASS2, text_color=ACCENT_SOFT)
            self.top_status.configure(text="HUD INTERACTIF")
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
        main = str(Path(__file__).resolve().parent.parent / "main.py")
        try:
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
        self.top_status.configure(text="SOUS LES APPS")
        if hasattr(self, "desk_mode_btn"):
            self.desk_mode_btn.configure(text="BUREAU LIBRE", fg_color=GLASS2, text_color=ACCENT_SOFT)

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
        # Barre supérieure
        top = ctk.CTkFrame(self.root, fg_color=BG_DEEP, height=36, corner_radius=0)
        top.pack(fill="x")
        top.pack_propagate(False)
        ctk.CTkLabel(top, text=f"◈ {NOM_IA_AFFICHE} NEURAL INTERFACE v{KIT_VERSION}", font=self.font_hud_b, text_color=ACCENT).pack(side="left", padx=16)
        self.top_status = ctk.CTkLabel(top, text="BOOT...", font=self.font_hud, text_color=TEXT_MUTED)
        self.top_status.pack(side="right", padx=16)
        modele = getattr(self.hub.brain, "modele", MODELE_GEMINI)
        ctk.CTkLabel(top, text=f"MODÈLE · {modele}", font=self.font_sub, text_color=TEXT_MUTED).pack(side="right", padx=8)

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

        ctk.CTkLabel(panel, text="TÉLÉMÉTRIE", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(16, 8))

        self.clock_label = ctk.CTkLabel(panel, text="--:--", font=self.font_clock, text_color=ACCENT)
        self.clock_label.pack(anchor="w", padx=14)
        self.date_label = ctk.CTkLabel(panel, text="—", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.date_label.pack(anchor="w", padx=14, pady=(0, 12))

        ctk.CTkFrame(panel, fg_color=LINE, height=1).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(panel, text="SYSTÈME", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(8, 4))
        self.cpu_label = ctk.CTkLabel(panel, text="CPU  — %", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.cpu_label.pack(anchor="w", padx=14)
        self.ram_label = ctk.CTkLabel(panel, text="RAM  — %", font=self.font_hud, text_color=TEXT_SECONDARY)
        self.ram_label.pack(anchor="w", padx=14, pady=(0, 8))

        ctk.CTkFrame(panel, fg_color=LINE, height=1).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(panel, text="LOCALISATION", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(8, 4))
        ctk.CTkLabel(panel, text=f"📍 {VILLE_DEFAUT}", font=self.font_hud, text_color=TEXT_SECONDARY).pack(anchor="w", padx=14)

        ctk.CTkFrame(panel, fg_color=LINE, height=1).pack(fill="x", padx=12, pady=4)

        ctk.CTkLabel(panel, text="MODULES", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(8, 4))
        self.module_labels = {}
        self.module_status_labels = {}
        for nom, statut in MODULES:
            row = ctk.CTkFrame(panel, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=1)
            if nom == "Gmail":
                couleur, etat = TEXT_MUTED, "○ …"
            elif statut == "online":
                couleur, etat = SUCCESS, "● ONLINE"
            elif statut == "micro" and MICRO_DISPONIBLE:
                couleur, etat = ACCENT_WARN, "● READY"
            else:
                couleur, etat = TEXT_MUTED, "○ OFFLINE"
            etat_lbl = ctk.CTkLabel(row, text=etat, font=self.font_sub, text_color=couleur, width=70)
            etat_lbl.pack(side="left")
            lbl = ctk.CTkLabel(row, text=nom, font=self.font_hud, text_color=TEXT_SECONDARY)
            lbl.pack(side="left")
            self.module_labels[nom] = lbl
            self.module_status_labels[nom] = etat_lbl

        ctk.CTkFrame(panel, fg_color=LINE, height=1).pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(panel, text="📱 CONTRÔLE MOBILE", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(8, 4))

        ip = obtenir_ip_wifi()
        self.remote_url_wifi = f"http://{ip}:{REMOTE_PORT}"
        self.remote_url = self.remote_url_wifi

        ctk.CTkLabel(panel, text="WiFi (maison)", font=self.font_sub, text_color=TEXT_MUTED).pack(anchor="w", padx=14)
        self.wifi_label = ctk.CTkLabel(
            panel, text=self.remote_url_wifi, font=self.font_hud, text_color=ACCENT_SOFT,
            cursor="hand2", wraplength=190, justify="left",
        )
        self.wifi_label.pack(anchor="w", padx=14)
        self.wifi_label.bind("<Button-1>", lambda e: self._copier_url(self.remote_url_wifi))

        ctk.CTkLabel(panel, text="Internet (4G/partout)", font=self.font_sub, text_color=ACCENT).pack(anchor="w", padx=14, pady=(6, 0))
        self.tunnel_label = ctk.CTkLabel(
            panel, text="Connexion ngrok...", font=ctk.CTkFont(family="Consolas", size=10),
            text_color=ACCENT_WARN, wraplength=200, justify="left",
        )
        self.tunnel_label.pack(anchor="w", padx=14, pady=(2, 4))

        ctk.CTkButton(
            panel, text="📋 Copier URL Internet", font=self.font_hud_b,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=BG_DEEP,
            height=32, corner_radius=8,
            command=lambda: self._copier_url(self.remote_url),
        ).pack(fill="x", padx=12, pady=(0, 4))

        ctk.CTkButton(
            panel, text="🌐 Ouvrir dans le navigateur", font=self.font_hud,
            fg_color=BG_PANEL2, hover_color=ACCENT_DIM, text_color=TEXT_SECONDARY,
            height=30, corner_radius=8,
            command=self._ouvrir_url_navigateur,
        ).pack(fill="x", padx=12, pady=(0, 6))

        ctk.CTkLabel(panel, text=f"PIN · {REMOTE_PIN}", font=self.font_hud_b, text_color=ACCENT).pack(anchor="w", padx=14, pady=(2, 0))
        self.remote_clients_label = ctk.CTkLabel(panel, text="Serveur...", font=self.font_sub, text_color=TEXT_MUTED)
        self.remote_clients_label.pack(anchor="w", padx=14, pady=(2, 2))
        ctk.CTkLabel(
            panel, text="Tél → onglet ÉCRAN = live PC",
            font=self.font_sub, text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=14)

    def _panel_centre(self, parent):
        centre = ctk.CTkFrame(parent, fg_color=BG_MAIN, corner_radius=0)
        centre.grid(row=0, column=1, sticky="nsew")
        centre.grid_rowconfigure(2, weight=1)
        centre.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(centre, text="A S T A T", font=self.font_title, text_color=ACCENT).grid(row=0, pady=(12, 0))
        self.status_label = ctk.CTkLabel(centre, text="initialisation...", font=self.font_sub, text_color=TEXT_MUTED)
        self.status_label.grid(row=1, pady=(2, 4))

        orb_frame = ctk.CTkFrame(centre, fg_color=BG_DEEP, corner_radius=120, width=230, height=230)
        orb_frame.grid(row=2, pady=4)
        orb_frame.pack_propagate(False)
        self.hud_canvas = HudCanvas(orb_frame, size=220)
        self.hud_canvas.pack(expand=True)
        self.hud_canvas.bind("<Double-Button-1>", lambda e: self.start_listening())

        # Mission log
        log_frame = ctk.CTkFrame(centre, fg_color=BG_PANEL2, corner_radius=12)
        log_frame.grid(row=3, sticky="nsew", padx=20, pady=(4, 12))
        centre.grid_rowconfigure(3, weight=1)

        hdr = ctk.CTkFrame(log_frame, fg_color="transparent")
        hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(hdr, text="◆ MISSION LOG", font=self.font_hud_b, text_color=ACCENT_DIM).pack(side="left")
        self.thinking_label = ctk.CTkLabel(hdr, text="", font=self.font_hud, text_color=ACCENT_SOFT)
        self.thinking_label.pack(side="right")

        self.zone_chat = ctk.CTkScrollableFrame(log_frame, fg_color="transparent")
        self.zone_chat.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _panel_droit(self, parent):
        panel = ctk.CTkFrame(parent, fg_color=BG_PANEL, width=240, corner_radius=0)
        panel.grid(row=0, column=2, sticky="nsew")
        panel.pack_propagate(False)

        ctk.CTkLabel(panel, text="ACTIONS RAPIDES", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(16, 8))

        grid = ctk.CTkFrame(panel, fg_color="transparent")
        grid.pack(fill="x", padx=10)

        for i, (label, cmd) in enumerate(QUICK_ACTIONS):
            btn = ctk.CTkButton(
                grid, text=label, font=self.font_hud,
                fg_color=BG_PANEL2, hover_color=ACCENT_DIM,
                border_color=LINE, border_width=1,
                text_color=TEXT_PRIMARY, height=34, corner_radius=8,
                command=lambda c=cmd: self._action_rapide(c),
            )
            btn.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(panel, fg_color=LINE, height=1).pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(panel, text="PROTOCOLES", font=self.font_hud_b, text_color=ACCENT_DIM).pack(anchor="w", padx=14, pady=(0, 8))

        self.toggle_button = ctk.CTkButton(
            panel, text=f"🎧 Écoute « {MOT_MAGIQUE} »",
            font=self.font_hud, fg_color=BG_PANEL2, hover_color=ACCENT_DIM,
            border_color=ACCENT_DIM, border_width=1, text_color=ACCENT_SOFT,
            height=36, corner_radius=8, command=self.toggle_background_listening,
        )
        self.toggle_button.pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(
            panel, text="⛶ Plein écran  (F11)", font=self.font_hud,
            fg_color=BG_PANEL2, hover_color=ACCENT_DIM, text_color=TEXT_SECONDARY,
            height=32, corner_radius=8, command=self._toggle_fullscreen,
        ).pack(fill="x", padx=12, pady=4)

        ctk.CTkButton(
            panel, text="🎤 Parler", font=self.font_hud_b,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=BG_DEEP,
            height=40, corner_radius=8, command=self.start_listening,
        ).pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            panel, text="Double-clic sur le noyau\npour parler",
            font=self.font_sub, text_color=TEXT_MUTED, justify="center",
        ).pack(pady=8)

    def _barre_commande(self):
        barre = ctk.CTkFrame(self.root, fg_color=BG_DEEP, height=58, corner_radius=0)
        barre.pack(fill="x", side="bottom")
        barre.pack_propagate(False)

        inner = ctk.CTkFrame(barre, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=10)

        ctk.CTkLabel(inner, text="▸", font=self.font_hud_b, text_color=ACCENT).pack(side="left", padx=(0, 8))

        self.entry = ctk.CTkEntry(
            inner, placeholder_text=f"Commande {NOM_IA}...  (Ctrl+K)",
            fg_color=BG_INPUT, border_color=ACCENT_DIM, border_width=1,
            text_color=TEXT_PRIMARY, font=self.font_chat, height=38, corner_radius=8,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", self.send_text_message)

        self.mic_button = ctk.CTkButton(
            inner, text="🎤", width=42, height=38, corner_radius=8,
            fg_color=BG_PANEL2, hover_color=ACCENT_DIM, text_color=ACCENT,
            command=self.start_listening,
        )
        self.mic_button.pack(side="left")

    # ── Animations & telemetry ────────────────────────────────────

    def _demarrer_boot(self):
        etapes = [
            "chargement modules neuronaux…",
            "liaison gemini…",
            "calibration vocale…",
            "vérification gmail…",
            "hud en ligne.",
        ]
        self._boot_step(0, etapes)

    def _boot_step(self, i, etapes):
        if i < len(etapes):
            msg = etapes[i]
            self.status_label.configure(text=msg)
            self.top_status.configure(text=f"BOOT {int((i + 1) / len(etapes) * 100)}%")
            if self._boot_overlay and self._boot_sub:
                self._boot_sub.configure(text=msg.upper())
            self.root.after(420, lambda: self._boot_step(i + 1, etapes))
        else:
            self.boot_done = True
            self.top_status.configure(
                text="HUD ONLINE" if self.desktop_mode else "SYSTEMS ONLINE"
            )
            self.definir_etat("idle", "en attente de vos ordres")
            self._dismiss_boot_overlay()
            self._verifier_gmail_au_demarrage()
            if self.desktop_mode:
                self.root.after(
                    600,
                    lambda: self.ajouter_bulle(
                        "astat",
                        "HUD v4 en ligne. Double-clic sur le noyau pour parler — F8 pour le bureau.",
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
                lbl.configure(text="ON", text_color=SUCCESS)
                self.ajouter_bulle("astat", "Gmail déjà connecté.")
            else:
                lbl.configure(text="OFF", text_color=ACCENT_WARN)
                self.ajouter_bulle("astat", "Gmail non lié — dis « connecte Gmail » une fois.")

    def _tick_horloge(self):
        now = datetime.datetime.now()
        self.clock_label.configure(text=now.strftime("%H:%M:%S"))
        jours = ["LUN", "MAR", "MER", "JEU", "VEN", "SAM", "DIM"]
        mois = ["JAN", "FÉV", "MAR", "AVR", "MAI", "JUN", "JUL", "AOÛ", "SEP", "OCT", "NOV", "DÉC"]
        self.date_label.configure(text=f"{jours[now.weekday()]}  ·  {now.day} {mois[now.month - 1]}  ·  {now.year}")
        self.root.after(1000, self._tick_horloge)

    def _tick_telemetry(self):
        if PSUTIL_OK:
            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent
            if self.cpu_meter:
                self.cpu_meter.set_value(cpu)
            if self.ram_meter:
                self.ram_meter.set_value(ram)
            if self.cpu_label.winfo_exists():
                try:
                    self.cpu_label.configure(text="")
                    self.ram_label.configure(text="")
                except Exception:
                    pass
        elif self.cpu_meter:
            self.cpu_meter.set_value(0)
            self.ram_meter.set_value(0)
        n = self.hub.remote_clients
        self.remote_clients_label.configure(
            text=f"{n} tél. lié(s)" if n else "aucun tél. lié",
            text_color=SUCCESS if n else TEXT_MUTED,
        )
        self._maj_tunnel_ui()
        self.root.after(2500, self._tick_telemetry)

    def _maj_tunnel_ui(self):
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
        statut = f"écoute permanente · « {MOT_MAGIQUE} »" if self.listening_active else "en attente de vos ordres"
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
        couleur_tag = ACCENT if est_astat else TEXT_MUTED

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
                txt = f"en écoute · « {MOT_MAGIQUE} »" if self.listening_active else "en attente de vos ordres"
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
                mic, self.on_background_audio, phrase_time_limit=10
            )
            self.listening_active = True
            self.toggle_button.configure(text="ÉCOUTE ACTIVE", fg_color=ACCENT_DIM, text_color=BG_DEEP)
            self.definir_etat("listening", f"écoute permanente · « {MOT_MAGIQUE} »")
        else:
            if self.stop_background_listening:
                self.stop_background_listening(wait_for_stop=False)
            self.listening_active = False
            self.toggle_button.configure(
                text=f"ÉCOUTE  « {MOT_MAGIQUE.upper()} »", fg_color=GLASS2, text_color=ACCENT_SOFT,
            )
            self.definir_etat("idle", "en attente de vos ordres")

    def on_background_audio(self, recognizer, audio):
        try:
            texte = recognizer.recognize_google(audio, language="fr-FR")
        except (sr.UnknownValueError, sr.RequestError):
            return

        if MOT_MAGIQUE not in texte.lower():
            return

        AstatVoice.bip_activation()
        texte_min = texte.lower()
        index = texte_min.index(MOT_MAGIQUE) + len(MOT_MAGIQUE)
        commande = texte[index:].strip(" ,.!?") or "Oui, je t'écoute."
        threading.Thread(target=self.process_message, args=(commande, "local"), daemon=True).start()

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
            etat = "listening" if self.listening_active else "idle"
            statut = f"écoute permanente · « {MOT_MAGIQUE} »" if self.listening_active else "en attente de vos ordres"
            self.root.after(400, self.definir_etat, etat, statut)


def lancer():
    root = ctk.CTk()
    AstatApp(root, desktop_mode=DESKTOP_MODE)
    root.mainloop()
