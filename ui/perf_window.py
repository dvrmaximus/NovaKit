"""Vue Performance embarquee — style Metrics Adrenalin + Mode Performance + Conseiller IA."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import ui.hud_theme as theme
from core import mode_settings
from core import perf_advisor
from core import perf_boost
from core.perf_monitor import format_net, snapshot
from ui.hud_widgets import SectionTitle, mono
from ui.mode_shell import CORNER, HudModePanel, labeled_slider, labeled_switch
from ui.perf_widgets import MetricCard

# Couleurs series (CPU vert fixe ; GPU = accent utilisateur ; FPS cyan/blanc)
CPU_COLOR = "#4FD66A"
FPS_COLOR = "#C8E8F0"
RAM_COLOR = "#5B9CF5"


class PerfPanel(HudModePanel):
    """Contenu Performance — vit dans le panneau gauche du HUD."""

    def __init__(
        self,
        master,
        wraplength: int = 340,
        get_hud_fps: Callable | None = None,
        get_frame_ms: Callable | None = None,
        on_boost_changed: Callable | None = None,
        **kw,
    ):
        self._wrap = wraplength
        self._get_hud_fps = get_hud_fps
        self._get_frame_ms = get_frame_ms
        self._on_boost_changed = on_boost_changed
        self._tick_id = None
        self._active = False
        self._settings_ready = False
        self._cfg = mode_settings.get_section("perf")
        self._last_advice = None
        self._advice_cards: list[ctk.CTkFrame] = []

        self.v_show_cpu = ctk.BooleanVar(value=bool(self._cfg.get("show_cpu", True)))
        self.v_show_ram = ctk.BooleanVar(value=bool(self._cfg.get("show_ram", True)))
        self.v_show_gpu = ctk.BooleanVar(value=bool(self._cfg.get("show_gpu", True)))
        self.v_show_disk = ctk.BooleanVar(value=bool(self._cfg.get("show_disk", True)))
        self.v_show_net = ctk.BooleanVar(value=bool(self._cfg.get("show_net", True)))
        self.v_show_temps = ctk.BooleanVar(value=bool(self._cfg.get("show_temps", True)))
        self.v_show_fps = ctk.BooleanVar(value=bool(self._cfg.get("show_fps", True)))
        self.v_hz = ctk.DoubleVar(value=float(self._cfg.get("refresh_hz", 1.5)))
        self.v_alert_cpu = ctk.IntVar(value=int(self._cfg.get("alert_cpu", 90)))
        self.v_alert_ram = ctk.IntVar(value=int(self._cfg.get("alert_ram", 90)))
        self.v_alert_gpu = ctk.IntVar(value=int(self._cfg.get("alert_gpu", 95)))
        self.v_hist = ctk.IntVar(value=int(self._cfg.get("history_points", 60)))
        self.v_mode_perf = ctk.BooleanVar(value=bool(self._cfg.get("mode_performance", False)))
        self.v_boost_gm = ctk.BooleanVar(value=bool(self._cfg.get("boost_game_mode", True)))
        self.v_boost_bg = ctk.BooleanVar(value=bool(self._cfg.get("boost_lower_bg", False)))
        self.v_jeu = ctk.StringVar(value=str(self._cfg.get("advisor_last_game") or "jeu actuel"))
        saved_apps = set(self._cfg.get("boost_apps") or [])
        self._app_vars: dict[str, ctk.BooleanVar] = {}
        for key, _label in perf_boost.SAFE_BG_APPS:
            self._app_vars[key] = ctk.BooleanVar(value=key in saved_apps if saved_apps else key in ("discord", "chrome"))

        super().__init__(
            master,
            title="Performance",
            nav=[
                ("mesures", "Mesures"),
                ("reglage", "Reglage"),
                ("parametres", "Parametres"),
            ],
            **kw,
        )
        self._build_mesures()
        self._build_reglage()
        self._build_parametres()
        self._settings_ready = True
        self._sync_boost_status_ui()
        if self.v_mode_perf.get() and not perf_boost.is_active():
            # Pref persistee : reactiver au premier affichage
            self.after(200, self._apply_boost_from_toggle)

    # —— lifecycle ——

    def set_active(self, active: bool):
        self._active = bool(active)
        if self._active:
            self._schedule_tick()
        else:
            self._stop_tick()

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _schedule_tick(self):
        self._stop_tick()
        if not self._active:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._refresh()
        hz = float(self._cfg.get("refresh_hz", 1.5) or 1.5)
        # Mode Performance : ralentir un peu le polling Astat
        if perf_boost.is_active():
            hz = min(hz, 1.0)
        delay = max(280, int(1000 / max(0.5, hz)))
        self._tick_id = self.after(delay, self._schedule_tick)

    # —— Mesures (Adrenalin) ——

    def _build_mesures(self):
        page = self.page("mesures")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        pts = int(self._cfg.get("history_points", 60))
        gpu_col = theme.ACCENT

        self.card_fps = MetricCard(scroll, "FPS · HUD Astat")
        self.card_fps.pack(fill="x", pady=3)
        self.card_fps.add_row("fps", "Frequence d'image", color=FPS_COLOR, unit="FPS", ymax=240, max_points=pts)
        self.card_fps.add_row("ft", "Duree d'image", color=FPS_COLOR, unit="ms", ymax=50, max_points=pts)

        self.card_cpu = MetricCard(scroll, "CPU")
        self.card_cpu.pack(fill="x", pady=3)
        self.card_cpu.add_row("util", "Utilisation", color=CPU_COLOR, unit="%", ymax=100, max_points=pts)
        self.card_cpu.add_row("temp", "Temperature", color=CPU_COLOR, unit="°C", ymax=100, max_points=pts)

        self.card_gpu = MetricCard(scroll, "GPU")
        self.card_gpu.pack(fill="x", pady=3)
        self.card_gpu.add_row("util", "Utilisation", color=gpu_col, unit="%", ymax=100, max_points=pts)
        self.card_gpu.add_row("power", "Consommation", color=gpu_col, unit="W", ymax=350, max_points=pts)
        self.card_gpu.add_row("temp", "Temperature GPU", color=gpu_col, unit="°C", ymax=100, max_points=pts)
        self.card_gpu.add_row("vram", "Memoire GPU", color=gpu_col, unit="%", ymax=100, max_points=pts)

        self.card_ram = MetricCard(scroll, "Memoire systeme")
        self.card_ram.pack(fill="x", pady=3)
        self.card_ram.add_row("util", "Utilisation", color=RAM_COLOR, unit="%", ymax=100, max_points=pts)

        self.mesures_foot = ctk.CTkLabel(
            scroll, text="", font=mono(8), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=self._wrap,
        )
        self.mesures_foot.pack(anchor="w", pady=(6, 0))

    # —— Reglage (Mode Performance + Conseiller) ——

    def _build_reglage(self):
        page = self.page("reglage")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        SectionTitle(scroll, "Mode Performance").pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            scroll,
            text="Optimisations OS sures : plan Haute perf, Mode Jeu, anti-lag Astat "
                 "(charge fond). Pas de controle driver AMD Anti-Lag.",
            font=mono(8), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=self._wrap,
        ).pack(anchor="w", pady=(0, 6))

        labeled_switch(
            scroll, "Activer Mode Performance", self.v_mode_perf,
            command=self._on_mode_perf_toggle,
        ).pack(fill="x", pady=2)
        labeled_switch(
            scroll, "Mode Jeu Windows (registre)", self.v_boost_gm,
            command=self._persist_settings,
        ).pack(fill="x", pady=2)
        labeled_switch(
            scroll, "Baisser priorite apps cochees", self.v_boost_bg,
            command=self._persist_settings,
        ).pack(fill="x", pady=2)

        self.boost_status = ctk.CTkLabel(
            scroll, text="Inactif", font=mono(8), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=self._wrap,
        )
        self.boost_status.pack(anchor="w", pady=(6, 8))

        SectionTitle(scroll, "Apps de fond (optionnel)").pack(fill="x", pady=(4, 4))
        for key, label in perf_boost.SAFE_BG_APPS:
            labeled_switch(
                scroll, label, self._app_vars[key], command=self._persist_settings,
            ).pack(fill="x", pady=1)

        ctk.CTkLabel(
            scroll,
            text="Astuce : ne tue aucun processus systeme — priorite basse uniquement.",
            font=mono(8), text_color=theme.TEXT_MUTED,
            justify="left", wraplength=self._wrap,
        ).pack(anchor="w", pady=(6, 10))

        # Conseiller IA
        SectionTitle(scroll, "Conseiller IA").pack(fill="x", pady=(4, 6))
        self.score_lbl = ctk.CTkLabel(
            scroll, text="Score machine —", font=mono(12, True), text_color=theme.ACCENT_SOFT,
        )
        self.score_lbl.pack(anchor="w")
        self.profil_lbl = ctk.CTkLabel(
            scroll, text="Profil recommande —", font=mono(9), text_color=theme.TEXT_SECONDARY,
        )
        self.profil_lbl.pack(anchor="w", pady=(0, 6))

        jeu_row = ctk.CTkFrame(scroll, fg_color="transparent")
        jeu_row.pack(fill="x", pady=2)
        ctk.CTkLabel(jeu_row, text="Jeu", font=mono(9), text_color=theme.TEXT_SECONDARY).pack(side="left")
        self.jeu_entry = ctk.CTkEntry(
            jeu_row, textvariable=self.v_jeu, font=mono(9), height=26,
            corner_radius=CORNER, border_width=1, border_color=theme.LINE,
            fg_color=theme.BG_INPUT,
        )
        self.jeu_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(6, 4))
        ctk.CTkButton(
            btn_row, text="Analyser", font=mono(9, True), height=28,
            corner_radius=CORNER, fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT, text_color=theme.TEXT_PRIMARY,
            command=self._run_advisor,
        ).pack(side="left", expand=True, fill="x", padx=(0, 3))
        ctk.CTkButton(
            btn_row, text="Appliquer les conseils", font=mono(9, True), height=28,
            corner_radius=CORNER, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_SOFT, text_color=theme.BG_DEEP,
            command=self._apply_advice,
        ).pack(side="left", expand=True, fill="x", padx=(3, 0))

        self.advice_box = ctk.CTkFrame(scroll, fg_color="transparent")
        self.advice_box.pack(fill="x", pady=(8, 0))
        self.tip_ia_lbl = ctk.CTkLabel(
            scroll, text="", font=mono(8), text_color=theme.ACCENT_SOFT,
            justify="left", wraplength=self._wrap,
        )
        self.tip_ia_lbl.pack(anchor="w", pady=(6, 0))

        # Prefill score
        self.after(120, self._run_advisor_silent)

    # —— Parametres (Suivi) ——

    def _build_parametres(self):
        page = self.page("parametres")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        SectionTitle(scroll, "Suivi — visibilite").pack(fill="x", pady=(0, 6))
        for var, txt in (
            (self.v_show_fps, "FPS HUD"),
            (self.v_show_cpu, "CPU"),
            (self.v_show_gpu, "GPU / VRAM"),
            (self.v_show_ram, "RAM"),
            (self.v_show_disk, "Disque (pied de page)"),
            (self.v_show_net, "Reseau (pied de page)"),
            (self.v_show_temps, "Temperatures"),
        ):
            labeled_switch(scroll, txt, var, command=self._persist_settings).pack(fill="x", pady=2)

        SectionTitle(scroll, "Echantillonnage & alertes").pack(fill="x", pady=(12, 6))
        box, _ = labeled_slider(
            scroll, "Intervalle (Hz)", self.v_hz, 0.5, 4.0,
            command=self._persist_settings, fmt="{:.1f} Hz",
        )
        box.pack(fill="x", pady=4)
        for var, txt in (
            (self.v_alert_cpu, "Alerte CPU (%)"),
            (self.v_alert_ram, "Alerte RAM (%)"),
            (self.v_alert_gpu, "Alerte GPU (%)"),
        ):
            box, _ = labeled_slider(
                scroll, txt, var, 50, 100, command=self._persist_settings, fmt="{:.0f} %",
            )
            box.pack(fill="x", pady=4)
        box, _ = labeled_slider(
            scroll, "Points historique", self.v_hist, 20, 120,
            command=self._persist_settings, fmt="{:.0f}",
        )
        box.pack(fill="x", pady=4)

        SectionTitle(scroll, "Rappels anti-lag").pack(fill="x", pady=(12, 6))
        for tip in perf_boost.tips_fr():
            ctk.CTkLabel(
                scroll, text=f"· {tip}", font=mono(8), text_color=theme.TEXT_MUTED,
                justify="left", wraplength=self._wrap, anchor="w",
            ).pack(fill="x", pady=1)

    # —— Settings / boost ——

    def _selected_apps(self) -> list[str]:
        return [k for k, v in self._app_vars.items() if v.get()]

    def _persist_settings(self):
        if not getattr(self, "_settings_ready", False):
            return
        patch = {
            "perf": {
                "refresh_hz": float(self.v_hz.get()),
                "show_cpu": bool(self.v_show_cpu.get()),
                "show_ram": bool(self.v_show_ram.get()),
                "show_gpu": bool(self.v_show_gpu.get()),
                "show_disk": bool(self.v_show_disk.get()),
                "show_net": bool(self.v_show_net.get()),
                "show_temps": bool(self.v_show_temps.get()),
                "show_fps": bool(self.v_show_fps.get()),
                "alert_cpu": int(self.v_alert_cpu.get()),
                "alert_ram": int(self.v_alert_ram.get()),
                "alert_gpu": int(self.v_alert_gpu.get()),
                "history_points": int(self.v_hist.get()),
                "mode_performance": bool(self.v_mode_perf.get()),
                "boost_game_mode": bool(self.v_boost_gm.get()),
                "boost_lower_bg": bool(self.v_boost_bg.get()),
                "boost_apps": self._selected_apps(),
            },
        }
        mode_settings.save(patch)
        self._cfg = mode_settings.get_section("perf")
        pts = int(self._cfg.get("history_points", 60))
        for card in (self.card_fps, self.card_cpu, self.card_gpu, self.card_ram):
            card.set_max_points(pts)
        self._apply_card_visibility()
        self.set_status("ok")
        if self._active:
            self._schedule_tick()

    def _apply_card_visibility(self):
        cfg = self._cfg
        mapping = (
            (self.card_fps, "show_fps"),
            (self.card_cpu, "show_cpu"),
            (self.card_gpu, "show_gpu"),
            (self.card_ram, "show_ram"),
        )
        for card, key in mapping:
            try:
                card.pack_forget()
            except Exception:
                pass
        for card, key in mapping:
            try:
                if cfg.get(key, True):
                    card.pack(fill="x", pady=3, before=self.mesures_foot)
            except Exception:
                try:
                    if cfg.get(key, True):
                        card.pack(fill="x", pady=3)
                except Exception:
                    pass

    def _on_mode_perf_toggle(self):
        self._persist_settings()
        self._apply_boost_from_toggle()

    def _apply_boost_from_toggle(self):
        if self.v_mode_perf.get():
            perf_boost.enable(
                lower_bg=bool(self.v_boost_bg.get()),
                selected_apps=self._selected_apps(),
                enable_game_mode=bool(self.v_boost_gm.get()),
            )
        else:
            perf_boost.disable()
        self._sync_boost_status_ui()
        if self._on_boost_changed:
            try:
                self._on_boost_changed(perf_boost.is_active())
            except Exception:
                pass

    def _sync_boost_status_ui(self):
        st = perf_boost.status_summary()
        if st["active"]:
            txt = "ACTIF — " + " | ".join(st.get("lines") or ["optimisations OS"])
            col = theme.SUCCESS
        else:
            txt = "Inactif — active pour plan Haute perf + anti-lag Astat."
            col = theme.TEXT_MUTED
        try:
            self.boost_status.configure(text=txt, text_color=col)
            self.v_mode_perf.set(bool(st["active"] or self._cfg.get("mode_performance")))
        except Exception:
            pass

    # —— Conseiller ——

    def _run_advisor_silent(self):
        try:
            self._run_advisor(silent=True)
        except Exception:
            pass

    def _run_advisor(self, silent: bool = False):
        jeu = (self.v_jeu.get() or "").strip()
        pack = perf_advisor.build_advice(jeu)
        self._last_advice = pack
        self.score_lbl.configure(text=f"Score machine  {pack.score}/100")
        self.profil_lbl.configure(text=f"Profil recommande : {pack.profil}")
        self._render_advice_cards(pack)
        mode_settings.save({
            "perf": {
                "advisor_last_game": jeu,
                "advisor_last_score": pack.score,
                "advisor_last_profil": pack.profil,
            },
        })
        if not silent:
            self.set_status("conseils ok")
            self.tip_ia_lbl.configure(text="Tip IA…")

            def _done(tip: str):
                def _ui():
                    self.tip_ia_lbl.configure(
                        text=(f"IA : {tip}" if tip else "Heuristique locale (pas de tip cloud)."),
                    )
                try:
                    self.after(0, _ui)
                except Exception:
                    pass

            perf_advisor.fetch_gemini_tip_async(pack, on_done=_done)

    def _render_advice_cards(self, pack: perf_advisor.AdvicePack):
        for w in self._advice_cards:
            try:
                w.destroy()
            except Exception:
                pass
        self._advice_cards.clear()
        for i, line in enumerate(pack.cartes + [f"A fermer : {', '.join(pack.a_fermer)}"]):
            card = ctk.CTkFrame(
                self.advice_box, fg_color=theme.BG_PANEL,
                corner_radius=CORNER, border_width=1, border_color=theme.LINE,
            )
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(
                card, text=line, font=mono(8), text_color=theme.TEXT_PRIMARY,
                justify="left", wraplength=self._wrap, anchor="w",
            ).pack(fill="x", padx=8, pady=6)
            self._advice_cards.append(card)
            # Micro-animation : delai d'apparition
            card.pack_forget()
            self.after(40 * i, lambda c=card: self._safe_pack_advice(c))

    def _safe_pack_advice(self, card):
        try:
            if card.winfo_exists():
                card.pack(fill="x", pady=2)
        except Exception:
            pass

    def _apply_advice(self):
        if self._last_advice is None:
            self._run_advisor(silent=True)
        pack = self._last_advice
        if pack is None:
            return
        msg = perf_advisor.apply_advice(pack, enable_boost=True)
        self.v_mode_perf.set(perf_boost.is_active())
        self._cfg = mode_settings.get_section("perf")
        self._sync_boost_status_ui()
        if self._on_boost_changed:
            try:
                self._on_boost_changed(perf_boost.is_active())
            except Exception:
                pass
        self.tip_ia_lbl.configure(text=msg)
        self.set_status("applique")

    # —— Refresh ——

    def update_from_snap(self, snap) -> None:
        """Compat tick HUD externe."""
        if snap is None or not self._active:
            return
        try:
            self._push_snap(snap)
        except Exception:
            pass

    def _refresh(self):
        try:
            snap = snapshot()
        except Exception:
            return
        self._push_snap(snap)

    def _push_snap(self, snap):
        cfg = self._cfg
        alerts = []
        gpu_col = theme.ACCENT

        # Titres dynamiques
        cpu_title = snap.cpu_name or "CPU"
        self.card_cpu.set_title(cpu_title if len(cpu_title) < 42 else cpu_title[:40] + "…")
        gpu_title = snap.gpu_name or "GPU"
        self.card_gpu.set_title(gpu_title if len(gpu_title) < 42 else gpu_title[:40] + "…")

        # FPS
        if cfg.get("show_fps", True):
            fps = None
            ft = None
            if self._get_hud_fps:
                try:
                    v = float(self._get_hud_fps() or 0)
                    fps = v if v > 0 else None
                except Exception:
                    fps = None
            if self._get_frame_ms:
                try:
                    v = float(self._get_frame_ms() or 0)
                    ft = v if v > 0 else None
                except Exception:
                    ft = None
            self.card_fps.rows["fps"].update_metric(fps, unit="FPS")
            self.card_fps.rows["ft"].update_metric(ft, unit="ms")
            # Forcer couleur FPS
            self.card_fps.rows["fps"].gauge.set_colors(FPS_COLOR, theme.BG_PANEL2)
            self.card_fps.rows["fps"].spark.set_color(FPS_COLOR)

        if cfg.get("show_cpu", True):
            alert = snap.cpu_percent >= cfg.get("alert_cpu", 90)
            self.card_cpu.rows["util"].update_metric(snap.cpu_percent)
            if cfg.get("show_temps", True):
                self.card_cpu.rows["temp"].update_metric(snap.cpu_temp_c, unit="°C")
            else:
                self.card_cpu.rows["temp"].update_metric(None)
            if alert:
                alerts.append(f"CPU {snap.cpu_percent:.0f}%")

        if cfg.get("show_gpu", True):
            # Maj couleur accent GPU (peut changer runtime)
            for key in ("util", "power", "temp", "vram"):
                row = self.card_gpu.rows.get(key)
                if row:
                    row.gauge.set_colors(gpu_col, theme.BG_PANEL2)
                    row.spark.set_color(gpu_col)
            if snap.gpu_percent is not None:
                self.card_gpu.rows["util"].update_metric(snap.gpu_percent)
                if snap.gpu_percent >= cfg.get("alert_gpu", 95):
                    alerts.append(f"GPU {snap.gpu_percent:.0f}%")
            else:
                self.card_gpu.rows["util"].update_metric(None)
            self.card_gpu.rows["power"].update_metric(
                snap.gpu_power_w, unit="W",
            )
            if cfg.get("show_temps", True):
                self.card_gpu.rows["temp"].update_metric(snap.gpu_temp_c, unit="°C")
            else:
                self.card_gpu.rows["temp"].update_metric(None)
            self.card_gpu.rows["vram"].update_metric(snap.gpu_vram_percent)

        if cfg.get("show_ram", True):
            self.card_ram.rows["util"].update_metric(snap.ram_percent)
            if snap.ram_percent >= cfg.get("alert_ram", 90):
                alerts.append(f"RAM {snap.ram_percent:.0f}%")

        parts = [
            f"RAM {snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f} Go",
        ]
        if cfg.get("show_disk", True) and snap.disk_percent is not None:
            parts.append(f"Disque {snap.disk_percent:.0f}%")
        if cfg.get("show_net", True):
            parts.append(f"↓ {format_net(snap.net_down_kbps)}  ↑ {format_net(snap.net_up_kbps)}")
        if alerts:
            parts.append("Alertes : " + ", ".join(alerts))
        if perf_boost.is_active():
            parts.append("Mode Performance ON")
        self.mesures_foot.configure(text=" · ".join(parts))
        self.set_status(f"{cfg.get('refresh_hz', 1.5):.1f} Hz")


# —— Fenetre optionnelle (avance) ——

_PERF_WIN = None


def ouvrir_perf(master, on_close: Callable | None = None):
    """Ouvre une fenetre separee (avance) — UX par defaut = panneau in-HUD."""
    global _PERF_WIN
    from ui.mode_shell import ModeShell

    if _PERF_WIN is not None:
        try:
            if _PERF_WIN.winfo_exists():
                _PERF_WIN.lift_focus()
                return _PERF_WIN
        except Exception:
            _PERF_WIN = None

    class _Win(ModeShell):
        def __init__(self):
            super().__init__(
                master,
                title="Performance (avance)",
                subtitle="Vue detachee — preferer les onglets Astat",
                nav=[("main", "Contenu")],
                width=720,
                height=640,
                on_close=self._on_closed,
            )
            self.panel = PerfPanel(self.page("main"), wraplength=620)
            self.panel.pack(fill="both", expand=True)
            self.panel.set_active(True)

        def _on_closed(self):
            global _PERF_WIN
            try:
                self.panel.set_active(False)
            except Exception:
                pass
            _PERF_WIN = None
            if on_close:
                on_close()

    _PERF_WIN = _Win()
    return _PERF_WIN


def fermer_perf() -> None:
    global _PERF_WIN
    if _PERF_WIN is not None:
        try:
            if _PERF_WIN.winfo_exists():
                _PERF_WIN._fermer()
        except Exception:
            pass
    _PERF_WIN = None
