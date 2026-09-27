"""Vue Gaming embarquee dans Astat (presets, micro-bench, FPS)."""

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
from ui.mode_shell import CORNER, HudModePanel, LiveGraph, labeled_slider, labeled_switch

_RES_OPTIONS = ("auto", "1080p", "1440p", "4k")
_QUAL_OPTIONS = ("auto", "low", "medium", "high", "ultra")


class GamingPanel(HudModePanel):
    """Contenu Gaming — vit dans le panneau gauche du HUD."""

    def __init__(
        self,
        master,
        get_hud_fps: Callable | None = None,
        get_frame_ms: Callable | None = None,
        set_fps_tracking: Callable | None = None,
        on_bench_done: Callable | None = None,
        on_settings_changed: Callable | None = None,
        wraplength: int = 340,
        **kw,
    ):
        self._get_hud_fps = get_hud_fps
        self._get_frame_ms = get_frame_ms
        self._set_fps_tracking = set_fps_tracking
        self._on_bench_done = on_bench_done
        self._on_settings_changed = on_settings_changed
        self._wrap = wraplength
        self._tick_id = None
        self._active = False
        self._settings_ready = False
        self._cfg = mode_settings.get_section("gaming")
        self._last_estimates = []
        # Vars avant tout callback (bench slider appelle _persist_settings a la creation).
        self.v_res = ctk.StringVar(value=str(self._cfg.get("resolution_preset", "auto")))
        self.v_qual = ctk.StringVar(value=str(self._cfg.get("quality_preset", "auto")))
        self.v_bench_dur = ctk.DoubleVar(value=float(self._cfg.get("bench_duration_s", 2.5)))
        self.v_aggr = ctk.DoubleVar(value=float(self._cfg.get("aggressiveness", 0.5)))
        self.v_fps_ov = ctk.BooleanVar(value=bool(self._cfg.get("hud_fps_overlay", True)))

        super().__init__(
            master,
            title="Gaming",
            nav=[
                ("overview", "Resume"),
                ("presets", "Presets"),
                ("bench", "Bench"),
                ("settings", "Reglages"),
            ],
            **kw,
        )
        self._build_overview()
        self._build_presets()
        self._build_bench()
        self._build_settings()
        self._settings_ready = True

    def set_active(self, active: bool):
        self._active = bool(active)
        if self._active:
            self.after(80, self.refresh_hardware)
            self._apply_fps_tracking()
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
        self._tick_fps()
        self._tick_id = self.after(500, self._schedule_tick)

    def _build_overview(self):
        page = self.page("overview")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        fps_card = ctk.CTkFrame(
            scroll, fg_color=theme.BG_PANEL2, corner_radius=CORNER,
            border_width=1, border_color=theme.LINE,
        )
        fps_card.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            fps_card, text="FPS HUD", font=mono(8), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.fps_big = ctk.CTkLabel(
            fps_card, text="—", font=mono(28, True), text_color=theme.TEXT_PRIMARY,
        )
        self.fps_big.pack(anchor="w", padx=10)
        self.frame_lbl = ctk.CTkLabel(
            fps_card, text="frame — ms", font=mono(9), text_color=theme.TEXT_SECONDARY,
        )
        self.frame_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        hw_card = ctk.CTkFrame(
            scroll, fg_color=theme.BG_PANEL2, corner_radius=CORNER,
            border_width=1, border_color=theme.LINE,
        )
        hw_card.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(
            hw_card, text="Materiel", font=mono(8), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=10, pady=(8, 0))
        self.hw_lbl = ctk.CTkLabel(
            hw_card, text="Detection…", font=mono(9), text_color=theme.TEXT_SECONDARY,
            justify="left", wraplength=self._wrap,
        )
        self.hw_lbl.pack(anchor="w", padx=10, pady=(2, 8))

        self.g_fps = LiveGraph(scroll, title="FPS", unit="FPS", ymax=120, max_points=60, height=70)
        self.g_fps.pack(fill="x", pady=3)
        self.g_ft = LiveGraph(scroll, title="Frametime", unit="ms", ymax=40, max_points=60, height=64)
        self.g_ft.pack(fill="x", pady=3)

        ctk.CTkButton(
            scroll, text="Relire le PC", font=mono(9, True), height=28,
            corner_radius=CORNER, fg_color=theme.GLASS2, hover_color=theme.ACCENT_DIM,
            border_width=1, border_color=theme.LINE, text_color=theme.TEXT_SECONDARY,
            command=self.refresh_hardware,
        ).pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(
            scroll,
            text="Estimations indicatives — pas une mesure in-game.",
            font=mono(8), text_color=theme.TEXT_MUTED, wraplength=self._wrap, justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _build_presets(self):
        page = self.page("presets")
        SectionTitle(page, "Presets estimes").pack(fill="x", pady=(0, 4))
        filt = ctk.CTkFrame(page, fg_color="transparent")
        filt.pack(fill="x", pady=(0, 6))
        self.res_menu = ctk.CTkOptionMenu(
            filt, values=list(_RES_OPTIONS), variable=self.v_res,
            font=mono(9), fg_color=theme.GLASS2, button_color=theme.ACCENT_DIM,
            dropdown_fg_color=theme.BG_PANEL, command=lambda _: self._on_preset_filter(),
            width=90, corner_radius=CORNER, height=26,
        )
        self.res_menu.pack(side="left", padx=(0, 6))
        self.qual_menu = ctk.CTkOptionMenu(
            filt, values=list(_QUAL_OPTIONS), variable=self.v_qual,
            font=mono(9), fg_color=theme.GLASS2, button_color=theme.ACCENT_DIM,
            dropdown_fg_color=theme.BG_PANEL, command=lambda _: self._on_preset_filter(),
            width=90, corner_radius=CORNER, height=26,
        )
        self.qual_menu.pack(side="left")
        self.est_box = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.est_box.pack(fill="both", expand=True)

    def _build_bench(self):
        page = self.page("bench")
        SectionTitle(page, "Micro-bench CPU").pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(
            page,
            text="Charge synthetique legere. Annulable.",
            font=mono(9), text_color=theme.TEXT_SECONDARY, wraplength=self._wrap, justify="left",
        ).pack(anchor="w", pady=(0, 8))

        box, _ = labeled_slider(
            page, "Duree (s)", self.v_bench_dur, 1.0, 5.0,
            command=self._persist_settings, fmt="{:.1f} s",
        )
        box.pack(fill="x", pady=4)

        self.bench_btn = ctk.CTkButton(
            page, text="Lancer", font=mono(11, True), height=34,
            corner_radius=CORNER, fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT, text_color=theme.TEXT_PRIMARY,
            command=self._lancer_bench,
        )
        self.bench_btn.pack(fill="x", pady=(6, 4))
        self.bench_status = ctk.CTkLabel(page, text="", font=mono(9), text_color=theme.TEXT_MUTED)
        self.bench_status.pack(anchor="w", pady=2)
        self.bench_result = ctk.CTkLabel(
            page, text="", font=mono(12, True), text_color=theme.ACCENT_SOFT,
        )
        self.bench_result.pack(anchor="w", pady=(6, 0))

    def _build_settings(self):
        page = self.page("settings")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Estimations").pack(fill="x", pady=(0, 6))

        box, _ = labeled_slider(
            scroll, "Aggressivite", self.v_aggr, 0.0, 1.0,
            command=self._persist_settings, fmt="{:.0%}",
        )
        box.pack(fill="x", pady=4)

        labeled_switch(
            scroll, "Suivi FPS HUD", self.v_fps_ov, command=self._persist_settings,
        ).pack(fill="x", pady=4)

        ctk.CTkButton(
            scroll, text="Appliquer & recalculer", font=mono(10, True), height=30,
            corner_radius=CORNER, fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT, text_color=theme.TEXT_PRIMARY,
            command=self._persist_and_refresh,
        ).pack(anchor="w", pady=(10, 0))

    def _on_preset_filter(self):
        self._persist_settings()
        self._render_estimates(self._last_estimates)

    def _persist_settings(self):
        if not getattr(self, "_settings_ready", False):
            return
        patch = {
            "gaming": {
                "resolution_preset": self.v_res.get(),
                "quality_preset": self.v_qual.get(),
                "aggressiveness": float(self.v_aggr.get()),
                "hud_fps_overlay": bool(self.v_fps_ov.get()),
                "bench_duration_s": float(self.v_bench_dur.get()),
            },
        }
        mode_settings.save(patch)
        self._cfg = mode_settings.get_section("gaming")
        self._apply_fps_tracking()
        self.set_status("ok")
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

    def update_fps(self, fps: float | None, frame_ms: float | None = None):
        """Compat tick HUD externe."""
        if fps is None:
            self.fps_big.configure(text="—")
            return
        self.fps_big.configure(text=f"{fps:.0f}")
        if frame_ms is not None:
            self.frame_lbl.configure(text=f"frame  {frame_ms:.1f} ms")

    def set_hw_summary(self, text: str):
        try:
            self.hw_lbl.configure(text=text)
        except Exception:
            pass

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
            card = ctk.CTkFrame(
                self.est_box, fg_color=theme.BG_PANEL2, corner_radius=CORNER,
                border_width=1, border_color=theme.LINE,
            )
            card.pack(fill="x", pady=3)
            dim = False
            if res_f != "auto" and e.resolution.lower() != res_f:
                dim = True
            if qual_f != "auto" and e.qualite.lower() != qual_f:
                dim = True
            title_c = theme.TEXT_MUTED if dim else theme.TEXT_PRIMARY
            accent_c = theme.TEXT_MUTED if dim else theme.ACCENT_SOFT
            ctk.CTkLabel(
                card, text=e.scenario, font=mono(10, True), text_color=title_c,
            ).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(
                card,
                text=f"{e.resolution}  ·  ~{e.fps_cible} FPS  ·  {e.qualite}",
                font=mono(9), text_color=accent_c,
            ).pack(anchor="w", padx=10)
            ctk.CTkLabel(
                card, text=e.resume, font=mono(8), text_color=theme.TEXT_MUTED,
                wraplength=self._wrap, justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 8))
            shown += 1
        if shown == 0:
            ctk.CTkLabel(
                self.est_box, text="Aucune estimation.", font=mono(9), text_color=theme.TEXT_MUTED,
            ).pack(anchor="w")

    def _lancer_bench(self):
        if benchmark_en_cours():
            annuler_benchmark()
            self.bench_status.configure(text="Annulation…")
            return

        duree = float(self.v_bench_dur.get())
        self.bench_btn.configure(text="Stop")
        self.bench_status.configure(text="En cours…")
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
                self.bench_btn.configure(text="Lancer")
                if result.get("cancelled"):
                    self.bench_status.configure(text="Annule")
                    self.bench_result.configure(text="")
                else:
                    extra = f"  ·  HUD ~{avg_fps:.0f} FPS" if avg_fps else ""
                    self.bench_status.configure(text=f"OK {result.get('elapsed_s')} s{extra}")
                    self.bench_result.configure(
                        text=f"~{result['ops_m_per_s']} Mops/s"
                    )
                if self._on_bench_done:
                    self._on_bench_done(result, avg_fps)

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()


# —— Fenetre optionnelle (avance) ——

_GAMING_WIN = None


def ouvrir_gaming(
    master,
    get_hud_fps=None,
    get_frame_ms=None,
    set_fps_tracking=None,
    on_bench_done=None,
    on_close=None,
    on_settings_changed=None,
):
    global _GAMING_WIN
    from ui.mode_shell import ModeShell

    if _GAMING_WIN is not None:
        try:
            if _GAMING_WIN.winfo_exists():
                _GAMING_WIN.lift_focus()
                return _GAMING_WIN
        except Exception:
            _GAMING_WIN = None

    class _Win(ModeShell):
        def __init__(self):
            super().__init__(
                master,
                title="Gaming (avance)",
                subtitle="Vue detachee — preferer les onglets Astat",
                nav=[("main", "Contenu")],
                width=720,
                height=640,
                on_close=self._on_closed,
            )
            self.panel = GamingPanel(
                self.page("main"),
                get_hud_fps=get_hud_fps,
                get_frame_ms=get_frame_ms,
                set_fps_tracking=set_fps_tracking,
                on_bench_done=on_bench_done,
                on_settings_changed=on_settings_changed,
                wraplength=620,
            )
            self.panel.pack(fill="both", expand=True)
            self.panel.set_active(True)

        def _on_closed(self):
            global _GAMING_WIN
            try:
                self.panel.set_active(False)
            except Exception:
                pass
            _GAMING_WIN = None
            if on_close:
                on_close()

    _GAMING_WIN = _Win()
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


def fermer_tous() -> None:
    try:
        from ui.perf_window import fermer_perf
        fermer_perf()
    except Exception:
        pass
    fermer_gaming()
