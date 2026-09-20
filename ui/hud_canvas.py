"""Indicateur central futuriste — orbe à accent dynamique + perf idle."""

from __future__ import annotations

import math
import random
import tkinter as tk

import ui.hud_theme as theme


class HudCanvas(tk.Canvas):
    def __init__(self, master, size=220, bg=None, **kwargs):
        super().__init__(
            master, width=size, height=size,
            bg=bg or theme.BG_DEEP, highlightthickness=0, bd=0, **kwargs,
        )
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.phase = 0.0
        self.state = "idle"
        self.wave_heights = [0.2] * 12
        self._wave_tick = 0
        self._paused = False
        self._after_id = None
        self._last_label = ""
        self._items = {}  # ids réutilisables quand possible
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<Map>", lambda e: self._set_paused(False))
        self.bind("<Unmap>", lambda e: self._set_paused(True))
        self._animer()

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            # relance plus vite si sortie d'idle
            if not self._paused and self._after_id is None:
                self._animer()

    def _on_destroy(self, _event=None):
        self._paused = True
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _set_paused(self, paused: bool):
        self._paused = paused
        if not paused and self._after_id is None:
            try:
                if self.winfo_exists():
                    self._animer()
            except Exception:
                pass

    def _delay_ms(self) -> int:
        # Idle : ~10 fps ; actif : ~20 fps ; thinking : ~14 fps
        if self.state == "idle":
            return 100
        if self.state == "thinking":
            return 70
        return 50

    def _animer(self):
        self._after_id = None
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self._paused:
            return

        # Fenêtre minimisée / iconifiée : ralentir fortement
        try:
            top = self.winfo_toplevel()
            if str(top.state()) == "iconic":
                self._after_id = self.after(400, self._animer)
                return
        except Exception:
            pass

        accent = theme.ACCENT
        soft = theme.ACCENT_SOFT
        dim = theme.ACCENT_DIM
        glow = theme.ACCENT_GLOW
        line = theme.LINE
        bg = theme.BG_DEEP
        muted = theme.TEXT_MUTED
        success = theme.SUCCESS

        breath = 1.0 + 0.045 * math.sin(self.phase)
        glow_pulse = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(self.phase * 0.7))
        r = int(68 * breath)

        self.delete("all")

        # Halo extérieur (glow soft)
        halo_r = r + 28 + int(6 * glow_pulse)
        self.create_oval(
            self.cx - halo_r, self.cy - halo_r, self.cx + halo_r, self.cy + halo_r,
            outline=glow, width=2,
        )
        self.create_oval(
            self.cx - r - 16, self.cy - r - 16, self.cx + r + 16, self.cy + r + 16,
            outline=line, width=1,
        )
        self.create_oval(
            self.cx - r - 8, self.cy - r - 8, self.cx + r + 8, self.cy + r + 8,
            outline=dim, width=1,
        )

        col = {
            "idle": dim,
            "listening": soft,
            "speaking": accent,
            "thinking": success,
        }.get(self.state, dim)

        # Anneau principal
        self.create_oval(
            self.cx - r, self.cy - r, self.cx + r, self.cy + r,
            outline=col, width=2, fill=bg,
        )
        # Arc de scan (futuriste)
        if self.state != "idle":
            a0 = (self.phase * 40) % 360
            self.create_arc(
                self.cx - r - 4, self.cy - r - 4, self.cx + r + 4, self.cy + r + 4,
                start=a0, extent=70, style="arc", outline=accent, width=2,
            )

        nr = 7 if self.state == "idle" else 11
        self.create_oval(
            self.cx - nr, self.cy - nr, self.cx + nr, self.cy + nr,
            fill=col, outline="",
        )
        # Point chaud central
        if self.state in ("listening", "speaking"):
            hr = max(2, nr // 3)
            self.create_oval(
                self.cx - hr, self.cy - hr, self.cx + hr, self.cy + hr,
                fill=theme.ACCENT_HOT, outline="",
            )

        if self.state in ("listening", "speaking"):
            self._onde(col)

        label = {
            "idle": "prêt",
            "listening": "écoute",
            "speaking": "voix",
            "thinking": "…",
        }.get(self.state, "")
        self.create_text(
            self.cx, self.cy + r + 26, text=label, fill=muted, font=("Segoe UI", 9),
        )

        boost = {"idle": 0.55, "listening": 1.5, "speaking": 1.7, "thinking": 1.1}.get(
            self.state, 1.0
        )
        self.phase += 0.07 * boost
        self._after_id = self.after(self._delay_ms(), self._animer)

    def _onde(self, col):
        self._wave_tick += 1
        # regenerer hauteurs 1 frame sur 2 pour fluidité / CPU
        if self._wave_tick % 2 == 0:
            for i in range(12):
                self.wave_heights[i] = 0.25 + 0.55 * random.random()
        base_y = self.cy + 4
        step = 8
        x0 = self.cx - (12 * step) / 2
        for i, h in enumerate(self.wave_heights):
            x = x0 + i * step
            hh = 6 + h * 18
            self.create_line(x, base_y - hh, x, base_y + hh, fill=col, width=2)
