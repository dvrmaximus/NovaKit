"""Centre Gaming — config PC, presets, micro-bench, FPS (style Adrenalin)."""

from __future__ import annotations

import threading
from typing import Callable

import customtkinter as ctk

import ui.hud_theme as theme
from core import mode_settings
from core.gaming_estimate import (
    annuler_benchmark,
    benchmark_en_cours,
    detect_hardware,
    estimer_presets,
    micro_benchmark,
)
from ui.hud_widgets import SectionTitle, mono
from ui.mode_shell import LiveGraph, ModeShell, labeled_slider, labeled_switch

_GAMING_WIN: "GamingWindow | None" = None

_RES_OPTIONS = ("auto", "1080p", "1440p", "4k")
_QUAL_OPTIONS = ("auto", "low", "medium", "high", "ultra")


class GamingWindow(ModeShell):
    def __init__(
        self,
        master,
        get_hud_fps: Callable | None = None,
        get_frame_ms: Callable | None = None,
        set_fps_tracking: Callable | None = None,
        on_bench_done: Callable | None = None,
        on_close: Callable | None = None,
        on_settings_changed: Callable | None = None,
    ):
        self._get_hud_fps = get_hud_fps
        self._get_frame_ms = get_frame_ms
        self._set_fps_tracking = set_fps_tracking
        self._on_bench_done = on_bench_done
        self._on_settings_changed = on_settings_changed
        self._tick_id = None
        self._cfg = mode_settings.get_section("gaming")

        super().__init__(
            master,
            title="Centre Gaming",
            subtitle="Presets · FPS HUD · micro-bench",
            nav=[
                ("overview", "Vue d'ensemble"),
                ("presets", "Presets"),
                ("bench", "Micro-bench"),
                ("settings", "Reglages"),
            ],
            width=980,
            height=660,
            on_close=self._wrap_close(on_close),
        )
        self._build_overview()
        self._build_presets()
        self._build_bench()
        self._build_settings()
        self.after(150, self.refresh_hardware)
        self._schedule_tick()
        self._apply_fps_tracking()

    def _wrap_close(self, on_close):
        def _cb():
            global _GAMING_WIN
            self._stop_tick()
            _GAMING_WIN = None
            if on_close:
                on_close()
        return _cb

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _schedule_tick(self):
        self._stop_tick()
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._tick_fps()
        self._tick_id = self.after(500, self._schedule_tick)

    def _build_overview(self):
        page = self.page("overview")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        top = ctk.CTkFrame(scroll, fg_color="transparent")
        top.pack(fill="x")
        left = ctk.CTkFrame(top, fg_color=theme.BG_PANEL2, corner_radius=8)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(
            left, text="FPS HUD", font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.fps_big = ctk.CTkLabel(
            left, text="—", font=mono(36, True), text_color=theme.TEXT_PRIMARY,
        )
        self.fps_big.pack(anchor="w", padx=14)
        self.frame_lbl = ctk.CTkLabel(
            left, text="frame — ms", font=mono(10), text_color=theme.TEXT_SECONDARY,
        )
        self.frame_lbl.pack(anchor="w", padx=14, pady=(0, 12))

        right = ctk.CTkFrame(top, fg_color=theme.BG_PANEL2, corner_radius=8)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(
            right, text="Materiel", font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(12, 0))
        self.hw_lbl = ctk.CTkLabel(
            right, text="Detection…", font=mono(10), text_color=theme.TEXT_SECONDARY,
            justify="left", wraplength=360,
        )
        self.hw_lbl.pack(anchor="w", padx=14, pady=(4, 12))

        self.g_fps = LiveGraph(scroll, title="FPS (HUD)", unit="FPS", ymax=120, max_points=60, height=110)
        self.g_fps.pack(fill="x", pady=(12, 4))
        self.g_ft = LiveGraph(scroll, title="Frametime", unit="ms", ymax=40, max_points=60, height=90)
        self.g_ft.pack(fill="x", pady=4)

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            btn_row, text="Relire le PC", font=mono(10, True), height=32,
            fg_color=theme.GLASS2, hover_color=theme.ACCENT_DIM,
            border_width=1, border_color=theme.LINE, text_color=theme.TEXT_SECONDARY,
            command=self.refresh_hardware,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="Ouvrir presets", font=mono(10), height=32,
            fg_color=theme.ACCENT_DIM, hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY,
            command=lambda: self.show_page("presets"),
        ).pack(side="left")

        ctk.CTkLabel(
            scroll,
            text="Les estimations sont indicatives — pas une mesure in-game.",
            font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(12, 0))

    def _build_presets(self):
        page = self.page("presets")
        SectionTitle(page, "Estimations de presets").pack(fill="x", pady=(0, 6))
        filt = ctk.CTkFrame(page, fg_color="transparent")
        filt.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(filt, text="Resolution cible", font=mono(10), text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 8),
        )
        self.v_res = ctk.StringVar(value=str(self._cfg.get("resolution_preset", "auto")))
        self.res_menu = ctk.CTkOptionMenu(
            filt, values=list(_RES_OPTIONS), variable=self.v_res,
            font=mono(10), fg_color=theme.GLASS2, button_color=theme.ACCENT_DIM,
            dropdown_fg_color=theme.BG_PANEL, command=lambda _: self._on_preset_filter(),
            width=100,
        )
        self.res_menu.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(filt, text="Qualite", font=mono(10), text_color=theme.TEXT_MUTED).pack(
            side="left", padx=(0, 8),
        )
        self.v_qual = ctk.StringVar(value=str(self._cfg.get("quality_preset", "auto")))
        self.qual_menu = ctk.CTkOptionMenu(
            filt, values=list(_QUAL_OPTIONS), variable=self.v_qual,
            font=mono(10), fg_color=theme.GLASS2, button_color=theme.ACCENT_DIM,
            dropdown_fg_color=theme.BG_PANEL, command=lambda _: self._on_preset_filter(),
            width=110,
        )
        self.qual_menu.pack(side="left")

        self.est_box = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.est_box.pack(fill="both", expand=True)
        self._last_estimates = []

    def _build_bench(self):
        page = self.page("bench")
        SectionTitle(page, "Micro-benchmark CPU").pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            page,
            text="Charge synthetique legere (quelques secondes). Annulable. "
                 "Ne remplace pas un bench jeu.",
            font=mono(10), text_color=theme.TEXT_SECONDARY, wraplength=700, justify="left",
        ).pack(anchor="w", pady=(0, 10))

        self.v_bench_dur = ctk.DoubleVar(value=float(self._cfg.get("bench_duration_s", 2.5)))
        box, _ = labeled_slider(
            page, "Duree (s)", self.v_bench_dur, 1.0, 5.0,
            command=self._persist_settings, fmt="{:.1f} s",
        )
        box.pack(fill="x", pady=6)

        self.bench_btn = ctk.CTkButton(
            page, text="Lancer le micro-bench", font=mono(12, True), height=40,
            fg_color=theme.ACCENT_DIM, hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY, command=self._lancer_bench,
        )
        self.bench_btn.pack(fill="x", pady=(8, 4))
        self.bench_status = ctk.CTkLabel(page, text="", font=mono(11), text_color=theme.TEXT_MUTED)
        self.bench_status.pack(anchor="w", pady=4)
        self.bench_result = ctk.CTkLabel(
            page, text="", font=mono(14, True), text_color=theme.ACCENT_SOFT,
        )
        self.bench_result.pack(anchor="w", pady=(8, 0))

    def _build_settings(self):
        page = self.page("settings")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Estimations").pack(fill="x", pady=(0, 8))

        self.v_aggr = ctk.DoubleVar(value=float(self._cfg.get("aggressiveness", 0.5)))
        box, _ = labeled_slider(
            scroll,
            "Aggressivite estimation (prudent ← → optimiste)",
            self.v_aggr, 0.0, 1.0,
            command=self._persist_settings, fmt="{:.0%}",
        )
        box.pack(fill="x", pady=6)

        self.v_fps_ov = ctk.BooleanVar(value=bool(self._cfg.get("hud_fps_overlay", True)))
        labeled_switch(
            scroll, "Suivi FPS / frametime du HUD (overlay metriques)",
            self.v_fps_ov, command=self._persist_settings,
        ).pack(fill="x", pady=6)

        SectionTitle(scroll, "Fenetre").pack(fill="x", pady=(16, 8))
        gl = mode_settings.get_section("global")
        self.v_top = ctk.BooleanVar(value=bool(gl.get("always_on_top")))
        self.v_open = ctk.BooleanVar(value=bool(gl.get("open_window_on_mode", True)))
        self.v_opacity = ctk.DoubleVar(value=float(gl.get("opacity", 0.96)))
        labeled_switch(scroll, "Toujours au premier plan", self.v_top, command=self._persist_settings).pack(
            fill="x", pady=3,
        )
        labeled_switch(
            scroll, "Ouvrir ce panneau au passage en mode Gaming", self.v_open,
            command=self._persist_settings,
        ).pack(fill="x", pady=3)
        box, _ = labeled_slider(
            scroll, "Opacite panneau", self.v_opacity, 0.55, 1.0,
            command=self._persist_settings, fmt="{:.0%}",
        )
        box.pack(fill="x", pady=6)

        ctk.CTkButton(
            scroll, text="Appliquer & recalculer", font=mono(11, True), height=34,
            fg_color=theme.ACCENT_DIM, hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY, command=self._persist_and_refresh,
        ).pack(anchor="w", pady=(12, 0))

    def _on_preset_filter(self):
        self._persist_settings()
        self._render_estimates(self._last_estimates)

    def _persist_settings(self):
        patch = {
            "gaming": {
                "resolution_preset": self.v_res.get(),
                "quality_preset": self.v_qual.get(),
                "aggressiveness": float(self.v_aggr.get()),
                "hud_fps_overlay": bool(self.v_fps_ov.get()),
                "bench_duration_s": float(self.v_bench_dur.get()),
            },
            "global": {
                "always_on_top": bool(self.v_top.get()),
                "open_window_on_mode": bool(self.v_open.get()),
                "opacity": float(self.v_opacity.get()),
            },
        }
        mode_settings.save(patch)
        self._cfg = mode_settings.get_section("gaming")
        self.apply_window_prefs()
        self._apply_fps_tracking()
        self.set_status("reglages enregistres")
        if self._on_settings_changed:
            try:
                self._on_settings_changed()
            except Exception:
                pass

    def _persist_and_refresh(self):
        self._persist_settings()
        self.refresh_hardware()

    def _apply_fps_tracking(self):
        if self._set_fps_tracking:
            try:
                self._set_fps_tracking(bool(self._cfg.get("hud_fps_overlay", True)))
            except Exception:
                pass

    def _tick_fps(self):
        fps = None
        ms = None
        if self._get_hud_fps:
            try:
                fps = float(self._get_hud_fps() or 0) or None
            except Exception:
                fps = None
        if self._get_frame_ms:
            try:
                ms = float(self._get_frame_ms() or 0) or None
            except Exception:
                ms = None
        if fps:
            self.fps_big.configure(text=f"{fps:.0f}")
            self.g_fps.push(fps)
        else:
            self.fps_big.configure(text="—")
        if ms:
            self.frame_lbl.configure(text=f"frame  {ms:.1f} ms")
            self.g_ft.push(ms)
        elif fps:
            self.frame_lbl.configure(text=f"frame  {1000.0 / fps:.1f} ms")

    def refresh_hardware(self):
        def work():
            try:
                hw = detect_hardware(force=True)
                aggr = float(mode_settings.get_section("gaming").get("aggressiveness", 0.5))
                est = estimer_presets(hw, aggressiveness=aggr)
                self.after(0, lambda: self._apply_hw(hw, est))
            except Exception as exc:
                self.after(0, lambda: self.hw_lbl.configure(text=f"Erreur : {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _apply_hw(self, hw, estimates):
        vram = f", {hw.gpu_vram_gb:.1f} Go VRAM" if hw.gpu_vram_gb else ""
        self.hw_lbl.configure(
            text=f"{hw.cpu_name}\n{hw.ram_gb:.0f} Go RAM · {hw.cpu_cores} thr\n{hw.gpu_name}{vram}"
        )
        self._last_estimates = estimates
        self._render_estimates(estimates)

    def _render_estimates(self, estimates):
        for w in self.est_box.winfo_children():
            w.destroy()
        res_f = (self.v_res.get() or "auto").lower()
        qual_f = (self.v_qual.get() or "auto").lower()
        shown = 0
        for e in estimates:
            if res_f != "auto" and e.resolution.lower() != res_f:
                # affiche quand meme avec note si filtre strict trop vide — on filtre soft
                pass
            card = ctk.CTkFrame(
                self.est_box, fg_color=theme.BG_PANEL2, corner_radius=8,
                border_width=1, border_color=theme.LINE,
            )
            card.pack(fill="x", pady=4)
            dim = False
            if res_f != "auto" and e.resolution.lower() != res_f:
                dim = True
            if qual_f != "auto" and e.qualite.lower() != qual_f:
                dim = True
            title_c = theme.TEXT_MUTED if dim else theme.TEXT_PRIMARY
            accent_c = theme.TEXT_MUTED if dim else theme.ACCENT_SOFT
            ctk.CTkLabel(
                card, text=e.scenario, font=mono(11, True), text_color=title_c,
            ).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(
                card,
                text=f"{e.resolution}  ·  ~{e.fps_cible} FPS  ·  {e.qualite} / shaders {e.shaders}",
                font=mono(10), text_color=accent_c,
            ).pack(anchor="w", padx=12)
            ctk.CTkLabel(
                card, text=e.resume, font=mono(9), text_color=theme.TEXT_MUTED,
                wraplength=700, justify="left",
            ).pack(anchor="w", padx=12, pady=(0, 10))
            shown += 1
        if shown == 0:
            ctk.CTkLabel(
                self.est_box, text="Aucune estimation.", font=mono(10), text_color=theme.TEXT_MUTED,
            ).pack(anchor="w")

    def _lancer_bench(self):
        if benchmark_en_cours():
            annuler_benchmark()
            self.bench_status.configure(text="Annulation…")
            return

        duree = float(self.v_bench_dur.get())
        self.bench_btn.configure(text="Stop")
        self.bench_status.configure(text="Simulation legere en cours…")
        self.bench_result.configure(text="")
        fps_samples: list[float] = []

        def work():
            def prog(_p):
                if self._get_hud_fps:
                    try:
                        f = float(self._get_hud_fps() or 0)
                        if f > 0:
                            fps_samples.append(f)
                    except Exception:
                        pass

            result = micro_benchmark(duree_s=duree, on_progress=prog)
            avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else None

            def done():
                self.bench_btn.configure(text="Lancer le micro-bench")
                if result.get("cancelled"):
                    self.bench_status.configure(text="Bench annule")
                    self.bench_result.configure(text="")
                else:
                    extra = f"  ·  HUD ~{avg_fps:.0f} FPS" if avg_fps else ""
                    self.bench_status.configure(text=f"Termine en {result.get('elapsed_s')} s{extra}")
                    self.bench_result.configure(
                        text=f"Score CPU  ~{result['ops_m_per_s']} Mops/s"
                    )
                if self._on_bench_done:
                    self._on_bench_done(result, avg_fps)

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()


def ouvrir_gaming(
    master,
    get_hud_fps=None,
    get_frame_ms=None,
    set_fps_tracking=None,
    on_bench_done=None,
    on_close=None,
    on_settings_changed=None,
) -> GamingWindow:
    global _GAMING_WIN
    if _GAMING_WIN is not None:
        try:
            if _GAMING_WIN.winfo_exists():
                _GAMING_WIN.lift_focus()
                return _GAMING_WIN
        except Exception:
            _GAMING_WIN = None
    _GAMING_WIN = GamingWindow(
        master,
        get_hud_fps=get_hud_fps,
        get_frame_ms=get_frame_ms,
        set_fps_tracking=set_fps_tracking,
        on_bench_done=on_bench_done,
        on_close=on_close,
        on_settings_changed=on_settings_changed,
    )
    return _GAMING_WIN


def fermer_gaming() -> None:
    global _GAMING_WIN
    if _GAMING_WIN is not None:
        try:
            if _GAMING_WIN.winfo_exists():
                _GAMING_WIN._fermer()
        except Exception:
            pass
    _GAMING_WIN = None


def gaming_ouverte() -> bool:
    try:
        return _GAMING_WIN is not None and bool(_GAMING_WIN.winfo_exists())
    except Exception:
        return False


def fermer_tous() -> None:
    try:
        from ui.perf_window import fermer_perf
        fermer_perf()
    except Exception:
        pass
    fermer_gaming()
