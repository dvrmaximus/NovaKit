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
        self._base_r = max(36, int(size * 0.31))
        self.phase = 0.0
        self.state = "idle"
        self.wave_heights = [0.2] * 10
        self._wave_tick = 0
        self._paused = False
        self._after_id = None
        self._last_draw_key = None
        self._idle_skip = 0
        self._fps = 0.0
        self._frame_ms = 0.0
        self._fps_times: list[float] = []
        self._fps_tracking = False
        self._eco_idle = False  # Mode Performance : idle encore plus lent
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<Map>", lambda e: self._set_paused(False))
        self.bind("<Unmap>", lambda e: self._set_paused(True))
        self._animer()

    def set_state(self, state: str):
        if state != self.state:
            self.state = state
            self._idle_skip = 0
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

    def set_fps_tracking(self, enabled: bool):
        self._fps_tracking = bool(enabled)
        if not enabled:
            self._fps_times.clear()
            self._fps = 0.0
            self._frame_ms = 0.0

    def set_eco_idle(self, enabled: bool):
        """Reduit encore le FPS idle (Mode Performance / anti-lag Astat)."""
        self._eco_idle = bool(enabled)

    def get_fps(self) -> float:
        return float(self._fps)

    def get_frame_ms(self) -> float:
        return float(self._frame_ms)

    def _note_frame(self):
        if not self._fps_tracking:
            return
        import time
        now = time.perf_counter()
        self._fps_times.append(now)
        # fenetre 1 s
        cutoff = now - 1.0
        self._fps_times = [t for t in self._fps_times if t >= cutoff]
        n = len(self._fps_times)
        if n >= 2:
            span = self._fps_times[-1] - self._fps_times[0]
            self._fps = (n - 1) / span if span > 0 else 0.0
            self._frame_ms = (span / (n - 1)) * 1000.0 if n > 1 else 0.0

    def _delay_ms(self) -> int:
        # Idle ~6 fps ; eco ~3 ; thinking ~12 ; actif ~16
        if self.state == "idle":
            return 320 if self._eco_idle else 160
        if self.state == "thinking":
            return 100 if self._eco_idle else 80
        return 80 if self._eco_idle else 60

    def _animer(self):
        self._after_id = None
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        if self._paused:
            return

        try:
            top = self.winfo_toplevel()
            if str(top.state()) == "iconic":
                self._after_id = self.after(800, self._animer)
                return
        except Exception:
            pass

        # Idle : saute 1 frame sur 2 (respiration déjà lente)
        if self.state == "idle":
            self._idle_skip ^= 1
            if self._idle_skip:
                self.phase += 0.035
                self._after_id = self.after(self._delay_ms(), self._animer)
                return

        accent = theme.ACCENT
        soft = theme.ACCENT_SOFT
        dim = theme.ACCENT_DIM
        glow = theme.ACCENT_GLOW
        line = theme.LINE
        bg = theme.BG_DEEP
        muted = theme.TEXT_MUTED
        success = theme.SUCCESS

        breath = 1.0 + 0.04 * math.sin(self.phase)
        glow_pulse = 0.55 + 0.4 * (0.5 + 0.5 * math.sin(self.phase * 0.7))
        r = int(self._base_r * breath)

        # Évite redraw identique (idle quasi-statique)
        draw_key = (self.state, r, int(glow_pulse * 8), accent, theme.ACCENT_DIM)
        if self.state == "idle" and draw_key == self._last_draw_key:
            self.phase += 0.04
            self._after_id = self.after(self._delay_ms(), self._animer)
            return
        self._last_draw_key = draw_key

        self.delete("all")
        self._note_frame()

        halo_r = r + max(18, self.size // 10) + int(5 * glow_pulse)
        self.create_oval(
            self.cx - halo_r, self.cy - halo_r, self.cx + halo_r, self.cy + halo_r,
            outline=glow, width=2,
        )
        self.create_oval(
            self.cx - r - 14, self.cy - r - 14, self.cx + r + 14, self.cy + r + 14,
            outline=line, width=1,
        )
        self.create_oval(
            self.cx - r - 7, self.cy - r - 7, self.cx + r + 7, self.cy + r + 7,
            outline=dim, width=1,
        )

        col = {
            "idle": dim,
            "listening": soft,
            "speaking": accent,
            "thinking": success,
        }.get(self.state, dim)

        self.create_oval(
            self.cx - r, self.cy - r, self.cx + r, self.cy + r,
            outline=col, width=2, fill=bg,
        )
        if self.state != "idle":
            a0 = (self.phase * 40) % 360
            self.create_arc(
                self.cx - r - 3, self.cy - r - 3, self.cx + r + 3, self.cy + r + 3,
                start=a0, extent=70, style="arc", outline=accent, width=2,
            )

        nr = 6 if self.state == "idle" else 10
        self.create_oval(
            self.cx - nr, self.cy - nr, self.cx + nr, self.cy + nr,
            fill=col, outline="",
        )
        if self.state in ("listening", "speaking"):
            hr = max(2, nr // 3)
            self.create_oval(
                self.cx - hr, self.cy - hr, self.cx + hr, self.cy + hr,
                fill=theme.ACCENT_HOT, outline="",
            )
            self._onde(col)

        label = {
            "idle": "prêt",
            "listening": "écoute",
            "speaking": "voix",
            "thinking": "…",
        }.get(self.state, "")
        self.create_text(
            self.cx, self.cy + r + max(18, self.size // 10),
            text=label, fill=muted, font=("Segoe UI", 9),
        )

        boost = {"idle": 0.5, "listening": 1.45, "speaking": 1.6, "thinking": 1.05}.get(
            self.state, 1.0
        )
        self.phase += 0.065 * boost
        self._after_id = self.after(self._delay_ms(), self._animer)

    def _onde(self, col):
        self._wave_tick += 1
        n = len(self.wave_heights)
        if self._wave_tick % 2 == 0:
            for i in range(n):
                self.wave_heights[i] = 0.25 + 0.55 * random.random()
        base_y = self.cy + 4
        step = max(6, self.size // 28)
        x0 = self.cx - (n * step) / 2
        for i, h in enumerate(self.wave_heights):
            x = x0 + i * step
            hh = 5 + h * 16
            self.create_line(x, base_y - hh, x, base_y + hh, fill=col, width=2)
