"""Onglets modes + exports des vues Performance / Gaming in-HUD."""

from __future__ import annotations

import customtkinter as ctk

import ui.hud_theme as theme
from ui.hud_widgets import mono
from ui.mode_shell import CORNER

# Re-export des panneaux embarques
from ui.perf_window import PerfPanel as PerformanceView  # noqa: F401
from ui.gaming_window import GamingPanel as GamingView  # noqa: F401


class ModeSwitcher(ctk.CTkFrame):
    """Onglets Assist | Perf | Gaming — barre haute Astat."""

    def __init__(self, master, on_select, current: str = "assist", **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._on_select = on_select
        self._btns: dict[str, ctk.CTkButton] = {}
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x")
        for key, label in (("assist", "Assist"), ("performance", "Perf"), ("gaming", "Gaming")):
            b = ctk.CTkButton(
                row,
                text=label,
                font=mono(10, True),
                height=26,
                corner_radius=CORNER,
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
