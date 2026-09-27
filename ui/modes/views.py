"""Vues Performance / Gaming pour le panneau gauche HUD."""

from __future__ import annotations

import threading
import time

import customtkinter as ctk

import ui.hud_theme as theme
from ui.hud_widgets import MeterBar, SectionTitle, mono


class ModeSwitcher(ctk.CTkFrame):
    """Onglets Assist | Perf | Gaming."""

    def __init__(self, master, on_select, current: str = "assist", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_select = on_select
        self._btns: dict[str, ctk.CTkButton] = {}
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        for key, label in (("assist", "Assist"), ("performance", "Perf"), ("gaming", "Game")):
            b = ctk.CTkButton(
                row,
                text=label,
                font=mono(9, True),
                height=26,
                corner_radius=6,
                border_width=1,
                border_color=theme.LINE,
                command=lambda k=key: self._click(k),
            )
            b.pack(side="left", expand=True, fill="x", padx=1)
            self._btns[key] = b
        self.set_active(current)

    def _click(self, key: str):
        self.set_active(key)
        if self._on_select:
            self._on_select(key)

    def set_active(self, key: str):
        for k, b in self._btns.items():
            if k == key:
                b.configure(
                    fg_color=theme.ACCENT_DIM,
                    text_color=theme.TEXT_PRIMARY,
                    border_color=theme.GLASS_BORDER_HOT,
                )
            else:
                b.configure(
                    fg_color=theme.GLASS2,
                    text_color=theme.TEXT_SECONDARY,
                    border_color=theme.LINE,
                )


class AssistExtras(ctk.CTkFrame):
    """Modules + mobile (contenu assist sous le switcher)."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)


class PerformanceView(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        SectionTitle(self, "Performance").pack(fill="x", pady=(0, 6))
        self.cpu_meter = MeterBar(self, "CPU")
        self.cpu_meter.pack(fill="x", pady=(0, 6))
        self.ram_meter = MeterBar(self, "RAM")
        self.ram_meter.pack(fill="x", pady=(0, 4))
        self.ram_detail = ctk.CTkLabel(self, text="", font=mono(9), text_color=theme.TEXT_MUTED)
        self.ram_detail.pack(anchor="w", pady=(0, 6))
        self.disk_meter = MeterBar(self, "Disque")
        self.disk_meter.pack(fill="x", pady=(0, 4))
        self.disk_detail = ctk.CTkLabel(self, text="", font=mono(9), text_color=theme.TEXT_MUTED)
        self.disk_detail.pack(anchor="w", pady=(0, 6))
        self.gpu_meter = MeterBar(self, "GPU")
        self.gpu_meter.pack(fill="x", pady=(0, 4))
        self.vram_meter = MeterBar(self, "VRAM")
        self.vram_meter.pack(fill="x", pady=(0, 4))
        self.gpu_name = ctk.CTkLabel(
            self, text="GPU —", font=mono(9), text_color=theme.TEXT_SECONDARY, wraplength=200, justify="left",
        )
        self.gpu_name.pack(anchor="w", pady=(0, 4))
        self.temps_lbl = ctk.CTkLabel(self, text="Temp. —", font=mono(9), text_color=theme.TEXT_MUTED)
        self.temps_lbl.pack(anchor="w", pady=(0, 4))
        self.net_lbl = ctk.CTkLabel(self, text="Reseau —", font=mono(9), text_color=theme.TEXT_MUTED)
        self.net_lbl.pack(anchor="w")

    def update_from_snap(self, snap) -> None:
        from core.perf_monitor import format_net

        self.cpu_meter.set_value(snap.cpu_percent)
        self.ram_meter.set_value(snap.ram_percent)
        self.ram_detail.configure(
            text=f"{snap.ram_used_gb:.1f} / {snap.ram_total_gb:.1f} Go"
            if snap.ram_total_gb else ""
        )
        if snap.disk_percent is not None:
            self.disk_meter.set_value(snap.disk_percent)
            if snap.disk_used_gb is not None and snap.disk_total_gb is not None:
                self.disk_detail.configure(
                    text=f"{snap.disk_used_gb:.0f} / {snap.disk_total_gb:.0f} Go"
                )
        else:
            self.disk_detail.configure(text="n/d")
        if snap.gpu_percent is not None:
            self.gpu_meter.set_value(snap.gpu_percent)
        else:
            self.gpu_meter.set_value(0)
            self.gpu_meter.value_lbl.configure(text="n/d", text_color=theme.TEXT_MUTED)
        if snap.gpu_vram_percent is not None:
            self.vram_meter.set_value(snap.gpu_vram_percent)
        else:
            self.vram_meter.set_value(0)
            self.vram_meter.value_lbl.configure(text="n/d", text_color=theme.TEXT_MUTED)
        gname = snap.gpu_name or "GPU non detecte"
        self.gpu_name.configure(text=gname)
        parts = []
        if snap.cpu_temp_c is not None:
            parts.append(f"CPU {snap.cpu_temp_c:.0f} C")
        if snap.gpu_temp_c is not None:
            parts.append(f"GPU {snap.gpu_temp_c:.0f} C")
        self.temps_lbl.configure(text="Temp. " + (" · ".join(parts) if parts else "n/d (Windows)"))
        self.net_lbl.configure(
            text=f"Reseau  ↓ {format_net(snap.net_down_kbps)}  ↑ {format_net(snap.net_up_kbps)}"
        )


class GamingView(ctk.CTkFrame):
    def __init__(self, master, get_hud_fps=None, on_bench_done=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._get_hud_fps = get_hud_fps
        self._on_bench_done = on_bench_done
        self._cards: list[ctk.CTkFrame] = []

        SectionTitle(self, "Gaming").pack(fill="x", pady=(0, 4))
        self.fps_lbl = ctk.CTkLabel(
            self, text="HUD  — FPS", font=mono(16, True), text_color=theme.TEXT_PRIMARY,
        )
        self.fps_lbl.pack(anchor="w")
        self.frame_lbl = ctk.CTkLabel(
            self, text="frame — ms", font=mono(9), text_color=theme.TEXT_MUTED,
        )
        self.frame_lbl.pack(anchor="w", pady=(0, 6))

        SectionTitle(self, "Materiel").pack(fill="x", pady=(4, 4))
        self.hw_lbl = ctk.CTkLabel(
            self, text="Detection…", font=mono(9), text_color=theme.TEXT_SECONDARY,
            wraplength=200, justify="left",
        )
        self.hw_lbl.pack(anchor="w", pady=(0, 6))

        SectionTitle(self, "Estimations").pack(fill="x", pady=(2, 4))
        self.est_box = ctk.CTkFrame(self, fg_color="transparent")
        self.est_box.pack(fill="x")
        ctk.CTkLabel(
            self,
            text="Indicatif — pas une mesure in-game.",
            font=mono(8),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", pady=(4, 6))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 0))
        self.bench_btn = ctk.CTkButton(
            btn_row,
            text="Micro-bench",
            font=mono(9, True),
            height=28,
            corner_radius=6,
            fg_color=theme.GLASS2,
            hover_color=theme.ACCENT_DIM,
            border_width=1,
            border_color=theme.LINE,
            text_color=theme.TEXT_SECONDARY,
            command=self._lancer_bench,
        )
        self.bench_btn.pack(side="left", expand=True, fill="x", padx=(0, 2))
        self.refresh_btn = ctk.CTkButton(
            btn_row,
            text="Relire PC",
            font=mono(9),
            height=28,
            corner_radius=6,
            fg_color=theme.GLASS2,
            hover_color=theme.ACCENT_DIM,
            border_width=1,
            border_color=theme.LINE,
            text_color=theme.TEXT_SECONDARY,
            command=self.refresh_hardware,
        )
        self.refresh_btn.pack(side="left", expand=True, fill="x", padx=(2, 0))
        self.bench_status = ctk.CTkLabel(self, text="", font=mono(8), text_color=theme.TEXT_MUTED)
        self.bench_status.pack(anchor="w", pady=(4, 0))

        self.after(200, self.refresh_hardware)

    def update_fps(self, fps: float | None, frame_ms: float | None = None):
        if fps is None:
            self.fps_lbl.configure(text="HUD  — FPS")
            return
        self.fps_lbl.configure(text=f"HUD  {fps:.0f} FPS")
        if frame_ms is not None:
            self.frame_lbl.configure(text=f"frame  {frame_ms:.1f} ms")

    def refresh_hardware(self):
        def work():
            try:
                from core.gaming_estimate import detect_hardware, estimer_presets
                hw = detect_hardware(force=True)
                est = estimer_presets(hw)
                self.after(0, lambda: self._apply_hw(hw, est))
            except Exception as exc:
                self.after(0, lambda: self.hw_lbl.configure(text=f"Erreur : {exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _apply_hw(self, hw, estimates):
        vram = f", {hw.gpu_vram_gb:.1f} Go VRAM" if hw.gpu_vram_gb else ""
        self.hw_lbl.configure(
            text=f"{hw.cpu_name}\n{hw.ram_gb:.0f} Go RAM · {hw.cpu_cores} thr\n{hw.gpu_name}{vram}"
        )
        for w in self.est_box.winfo_children():
            w.destroy()
        for e in estimates:
            card = ctk.CTkFrame(
                self.est_box,
                fg_color=theme.BG_PANEL2,
                corner_radius=6,
                border_width=1,
                border_color=theme.LINE,
            )
            card.pack(fill="x", pady=2)
            ctk.CTkLabel(
                card, text=e.scenario, font=mono(8, True), text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=6, pady=(4, 0))
            ctk.CTkLabel(
                card,
                text=f"{e.resolution} · ~{e.fps_cible} FPS · {e.qualite} / shaders {e.shaders}",
                font=mono(8),
                text_color=theme.ACCENT_SOFT,
            ).pack(anchor="w", padx=6)
            ctk.CTkLabel(
                card, text=e.resume, font=mono(8), text_color=theme.TEXT_MUTED,
                wraplength=190, justify="left",
            ).pack(anchor="w", padx=6, pady=(0, 4))

    def _lancer_bench(self):
        from core.gaming_estimate import annuler_benchmark, benchmark_en_cours, micro_benchmark

        if benchmark_en_cours():
            annuler_benchmark()
            self.bench_status.configure(text="Annulation…")
            return

        self.bench_btn.configure(text="Stop")
        self.bench_status.configure(text="Simulation legere…")
        fps_samples: list[float] = []

        def sample_fps():
            if self._get_hud_fps:
                f = self._get_hud_fps()
                if f:
                    fps_samples.append(f)

        def work():
            def prog(_p):
                sample_fps()

            result = micro_benchmark(duree_s=2.5, on_progress=prog)
            avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else None

            def done():
                self.bench_btn.configure(text="Micro-bench")
                if result.get("cancelled"):
                    self.bench_status.configure(text="Bench annule")
                else:
                    extra = f" · HUD ~{avg_fps:.0f} FPS" if avg_fps else ""
                    self.bench_status.configure(
                        text=f"Score CPU ~{result['ops_m_per_s']} Mops/s{extra}"
                    )
                if self._on_bench_done:
                    self._on_bench_done(result, avg_fps)

            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()
