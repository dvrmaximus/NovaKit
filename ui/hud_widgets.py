"""Widgets HUD — accent dynamique + ticks allégés."""

from __future__ import annotations

import customtkinter as ctk

import ui.hud_theme as theme
from ui.hud_theme import FONT_MONO, FONT_MONO_FALLBACK


def mono(size=11, bold=False):
    try:
        return ctk.CTkFont(family=FONT_MONO, size=size, weight="bold" if bold else "normal")
    except Exception:
        return ctk.CTkFont(family=FONT_MONO_FALLBACK, size=size, weight="bold" if bold else "normal")


class CornerGlass(ctk.CTkFrame):
    """Panneau verre simple."""

    def __init__(self, master, width=200, height=200, corner_radius=10, **kw):
        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=corner_radius,
            fg_color=kw.pop("fg_color", theme.GLASS),
            border_width=1,
            border_color=kw.pop("border_color", theme.GLASS_BORDER),
            **kw,
        )
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.place(x=0, y=0, relwidth=1, relheight=1)

    @property
    def body(self):
        return self._content


class SectionTitle(ctk.CTkFrame):
    def __init__(self, master, text: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkLabel(
            self, text=text, font=mono(10, True), text_color=theme.TEXT_MUTED,
        ).pack(side="left")
        self._rule = ctk.CTkFrame(self, fg_color=theme.LINE, height=1)
        self._rule.pack(side="left", fill="x", expand=True, padx=(10, 0), pady=7)

    def rafraichir_accent(self):
        try:
            self._rule.configure(fg_color=theme.LINE)
        except Exception:
            pass


class MeterBar(ctk.CTkFrame):
    def __init__(self, master, label: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=label, font=mono(10), text_color=theme.TEXT_SECONDARY).pack(side="left")
        self.value_lbl = ctk.CTkLabel(top, text="0%", font=mono(10), text_color=theme.TEXT_MUTED)
        self.value_lbl.pack(side="right")
        track = ctk.CTkFrame(self, fg_color="#0C1016", height=4, corner_radius=2)
        track.pack(fill="x", pady=(4, 0))
        self.fill = ctk.CTkFrame(track, fg_color=theme.ACCENT_DIM, height=4, corner_radius=2, width=1)
        self.fill.place(x=0, y=0, relheight=1)
        self._last_pct = -1.0
        self._last_w = 0

    def set_value(self, pct: float):
        pct = max(0.0, min(100.0, float(pct)))
        # skip si quasi inchangé
        if abs(pct - self._last_pct) < 0.4:
            return
        self._last_pct = pct
        color = theme.SUCCESS if pct < 70 else (theme.ACCENT_WARN if pct < 90 else theme.ACCENT_DANGER)
        self.value_lbl.configure(text=f"{pct:.0f}%", text_color=color)
        self.fill.configure(fg_color=color)
        w = max(1, int(max(self.winfo_width(), 40) * pct / 100))
        if w != self._last_w:
            self._last_w = w
            try:
                self.fill.configure(width=w)
            except Exception:
                pass


class StatusDot(ctk.CTkLabel):
    def __init__(self, master, **kw):
        super().__init__(master, text="●", font=mono(10), text_color=theme.TEXT_MUTED, **kw)
        self._phase = 0
        self._after_id = None
        self.bind("<Destroy>", self._on_destroy)
        self._tick()

    def _on_destroy(self, _e=None):
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self):
        self._after_id = None
        try:
            if not self.winfo_exists():
                return
            top = self.winfo_toplevel()
            if str(top.state()) == "iconic":
                self._after_id = self.after(500, self._tick)
                return
        except Exception:
            return
        self._phase = (self._phase + 1) % 16
        on = self._phase < 8
        self.configure(text_color=theme.ACCENT_SOFT if on else theme.TEXT_MUTED)
        self._after_id = self.after(220, self._tick)
