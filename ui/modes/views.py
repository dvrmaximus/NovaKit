"""Vues Resume Performance / Gaming pour le panneau gauche HUD (+ switcher)."""

from __future__ import annotations

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


class PerformanceView(ctk.CTkFrame):
    """Mini resume HUD — le centre detaille s'ouvre dans une fenetre separee."""

    def __init__(self, master, on_open_panel=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_open = on_open_panel
        SectionTitle(self, "Performance").pack(fill="x", pady=(0, 6))
        self.cpu_meter = MeterBar(self, "CPU")
        self.cpu_meter.pack(fill="x", pady=(0, 4))
        self.ram_meter = MeterBar(self, "RAM")
        self.ram_meter.pack(fill="x", pady=(0, 4))
        self.gpu_meter = MeterBar(self, "GPU")
        self.gpu_meter.pack(fill="x", pady=(0, 6))
        self.summary = ctk.CTkLabel(
            self, text="Telemetrie…", font=mono(9), text_color=theme.TEXT_MUTED,
            wraplength=200, justify="left",
        )
        self.summary.pack(anchor="w", pady=(0, 8))
        ctk.CTkButton(
            self,
            text="Ouvrir panneau",
            font=mono(10, True),
            height=30,
            corner_radius=6,
            fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY,
            command=self._open,
        ).pack(fill="x")
        ctk.CTkLabel(
            self,
            text="Graphes, seuils et capteurs dans le Centre Performance.",
            font=mono(8),
            text_color=theme.TEXT_MUTED,
            wraplength=200,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _open(self):
        if self._on_open:
            self._on_open()

    def update_from_snap(self, snap) -> None:
        from core.perf_monitor import format_net

        self.cpu_meter.set_value(snap.cpu_percent)
        self.ram_meter.set_value(snap.ram_percent)
        if snap.gpu_percent is not None:
            self.gpu_meter.set_value(snap.gpu_percent)
        else:
            self.gpu_meter.set_value(0)
            self.gpu_meter.value_lbl.configure(text="n/d", text_color=theme.TEXT_MUTED)
        parts = []
        if snap.cpu_temp_c is not None:
            parts.append(f"CPU {snap.cpu_temp_c:.0f}°C")
        if snap.gpu_temp_c is not None:
            parts.append(f"GPU {snap.gpu_temp_c:.0f}°C")
        net = f"↓ {format_net(snap.net_down_kbps)}"
        line = " · ".join(parts) if parts else "Temp. n/d"
        self.summary.configure(text=f"{line}\n{net}")


class GamingView(ctk.CTkFrame):
    """Mini resume HUD Gaming."""

    def __init__(self, master, on_open_panel=None, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_open = on_open_panel
        SectionTitle(self, "Gaming").pack(fill="x", pady=(0, 4))
        self.fps_lbl = ctk.CTkLabel(
            self, text="HUD  — FPS", font=mono(16, True), text_color=theme.TEXT_PRIMARY,
        )
        self.fps_lbl.pack(anchor="w")
        self.frame_lbl = ctk.CTkLabel(
            self, text="frame — ms", font=mono(9), text_color=theme.TEXT_MUTED,
        )
        self.frame_lbl.pack(anchor="w", pady=(0, 6))
        self.hw_lbl = ctk.CTkLabel(
            self, text="Ouvre le panneau pour presets & bench.", font=mono(9),
            text_color=theme.TEXT_SECONDARY, wraplength=200, justify="left",
        )
        self.hw_lbl.pack(anchor="w", pady=(0, 8))
        ctk.CTkButton(
            self,
            text="Ouvrir panneau",
            font=mono(10, True),
            height=30,
            corner_radius=6,
            fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY,
            command=self._open,
        ).pack(fill="x")

    def _open(self):
        if self._on_open:
            self._on_open()

    def update_fps(self, fps: float | None, frame_ms: float | None = None):
        if fps is None:
            self.fps_lbl.configure(text="HUD  — FPS")
            return
        self.fps_lbl.configure(text=f"HUD  {fps:.0f} FPS")
        if frame_ms is not None:
            self.frame_lbl.configure(text=f"frame  {frame_ms:.1f} ms")

    def set_hw_summary(self, text: str):
        self.hw_lbl.configure(text=text)
