"""Widgets HUD réutilisables — barres, titres, verre à coins."""

from __future__ import annotations

import customtkinter as ctk

from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_SOFT, GLASS, GLASS2, GLASS_BORDER,
    LINE, SUCCESS, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_MONO, FONT_MONO_FALLBACK,
)


def mono(size=11, bold=False):
    family = FONT_MONO
    try:
        return ctk.CTkFont(family=family, size=size, weight="bold" if bold else "normal")
    except Exception:
        return ctk.CTkFont(family=FONT_MONO_FALLBACK, size=size, weight="bold" if bold else "normal")


class CornerGlass(ctk.CTkFrame):
    """Panneau verre + coins HUD dessinés en overlay canvas mince."""

    def __init__(self, master, width=200, height=200, corner_radius=14, **kw):
        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=corner_radius,
            fg_color=kw.pop("fg_color", GLASS),
            border_width=1,
            border_color=kw.pop("border_color", GLASS_BORDER),
            **kw,
        )
        self._w = width
        self._h = height
        self._corners = ctk.CTkCanvas(
            self, width=width, height=height,
            bg=GLASS, highlightthickness=0, bd=0,
        )
        # Canvas coins en fond, widgets au-dessus
        self._corners.place(x=0, y=0, relwidth=1, relheight=1)
        self._draw_corners()
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.place(x=0, y=0, relwidth=1, relheight=1)
        self.bind("<Configure>", self._on_resize)

    @property
    def body(self):
        return self._content

    def _on_resize(self, event):
        if event.width < 20 or event.height < 20:
            return
        self._w, self._h = event.width, event.height
        self._corners.configure(width=event.width, height=event.height)
        self._draw_corners()

    def _draw_corners(self):
        c = self._corners
        c.delete("all")
        # Fond aligné
        c.create_rectangle(0, 0, self._w, self._h, fill=GLASS, outline="")
        m, L = 6, 16
        pts = [
            (m, m, m + L, m, m, m + L),
            (self._w - m, m, self._w - m - L, m, self._w - m, m + L),
            (m, self._h - m, m + L, self._h - m, m, self._h - m - L),
            (self._w - m, self._h - m, self._w - m - L, self._h - m, self._w - m, self._h - m - L),
        ]
        for x, y, x2, y2a, x3, y3 in pts:
            c.create_line(x, y, x2, y2a, fill=ACCENT, width=2)
            c.create_line(x, y, x3, y3, fill=ACCENT, width=2)
        # Ligne scan haute
        c.create_line(24, 3, self._w - 24, 3, fill=ACCENT_DIM, width=1)


class SectionTitle(ctk.CTkFrame):
    def __init__(self, master, text: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        ctk.CTkLabel(
            self, text="▸", font=mono(10, True), text_color=ACCENT,
        ).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            self, text=text.upper(), font=mono(10, True), text_color=ACCENT_SOFT,
        ).pack(side="left")
        ctk.CTkFrame(self, fg_color=LINE, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6,
        )


class MeterBar(ctk.CTkFrame):
    """Barre CPU/RAM animée."""

    def __init__(self, master, label: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=label, font=mono(10, True), text_color=TEXT_SECONDARY).pack(side="left")
        self.value_lbl = ctk.CTkLabel(top, text="—%", font=mono(10, True), text_color=ACCENT)
        self.value_lbl.pack(side="right")
        self.track = ctk.CTkFrame(self, fg_color=GLASS2, height=6, corner_radius=3)
        self.track.pack(fill="x", pady=(4, 0))
        self.track.pack_propagate(False)
        self.fill = ctk.CTkFrame(self.track, fg_color=ACCENT, height=6, corner_radius=3, width=4)
        self.fill.place(x=0, y=0, relheight=1.0)
        self._pct = 0.0

    def set_value(self, pct: float):
        pct = max(0.0, min(100.0, float(pct)))
        self._pct = pct
        self.value_lbl.configure(text=f"{pct:.0f}%")
        color = SUCCESS if pct < 70 else ("#FFB020" if pct < 90 else "#FF4D6A")
        self.fill.configure(fg_color=color)
        self.value_lbl.configure(text_color=color)
        self.after_idle(self._layout_fill)

    def _layout_fill(self):
        try:
            w = max(4, int(self.track.winfo_width() * self._pct / 100))
            self.fill.configure(width=w)
            self.fill.place(x=0, y=0, relheight=1.0)
        except Exception:
            pass


class StatusDot(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", width=12, height=12, **kw)
        self.dot = ctk.CTkLabel(self, text="●", font=mono(10), text_color=ACCENT_DIM)
        self.dot.pack()
        self._phase = 0
        self._alive = True
        self.after(80, self._pulse)

    def set_ok(self, ok: bool = True):
        self._alive = ok
        if not ok:
            self.dot.configure(text_color=TEXT_MUTED)

    def _pulse(self):
        if self._alive:
            self._phase = (self._phase + 1) % 20
            # alternance douce
            self.dot.configure(text_color=ACCENT if self._phase < 10 else ACCENT_DIM)
        try:
            self.after(90, self._pulse)
        except Exception:
            pass
