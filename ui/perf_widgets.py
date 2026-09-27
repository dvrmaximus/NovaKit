"""Widgets style Adrenalin — jauges anneau + sparklines area (Tk Canvas)."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

import ui.hud_theme as theme
from ui.hud_theme import _mix
from ui.hud_widgets import mono

# Charcoal Metrics (fidelite Adrenalin, local a la vue Perf)
CARD_BG = "#1C1C1C"
CARD_INNER = "#141414"
CARD_LINE = "#2A2A2A"
TRACK = "#333333"
CORNER_SQ = 0


class RingGauge(ctk.CTkFrame):
    """Anneau fin anti-aliase (arcs superposes) + valeur centree."""

    def __init__(
        self,
        master,
        size: int = 58,
        thickness: float = 2.6,
        color: str | None = None,
        bg: str | None = None,
        **kw,
    ):
        self._bg = bg or CARD_BG
        super().__init__(master, fg_color="transparent", width=size + 4, height=size, **kw)
        self.pack_propagate(False)
        self._size = size
        self._thickness = thickness
        self._color = color or theme.ACCENT
        self._pct = 0.0
        self._text = "—"
        self._unit = ""
        self.canvas = tk.Canvas(
            self, width=size, height=size, bg=self._bg,
            highlightthickness=0, bd=0,
        )
        self.canvas.place(x=0, y=0)
        self._redraw_ring()

    def set_colors(self, color: str, bg: str | None = None):
        self._color = color
        if bg:
            self._bg = bg
            try:
                self.canvas.configure(bg=bg)
            except Exception:
                pass
        self._redraw_ring()

    def set_value(
        self,
        pct: float | None,
        text: str | None = None,
        unit: str = "",
        *,
        vmax: float = 100.0,
    ):
        if pct is None:
            self._pct = 0.0
            self._text = "S.O."
            self._unit = ""
        else:
            vmax = max(1.0, float(vmax))
            self._pct = max(0.0, min(100.0, (float(pct) / vmax) * 100.0))
            self._text = text if text is not None else f"{pct:.0f}"
            self._unit = unit
        self._redraw_ring()

    def _redraw_ring(self):
        c = self.canvas
        c.delete("all")
        s = self._size
        pad = 3.5
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        # Piste (anneau gris)
        try:
            c.create_arc(
                x0, y0, x1, y1,
                start=90, extent=-359.9,
                style=tk.ARC, outline=TRACK, width=self._thickness + 0.4,
            )
        except Exception:
            pass
        extent = -max(0.4, min(359.9, self._pct * 3.599))
        if self._pct > 0.4:
            soft = _mix(self._bg, self._color, 0.55)
            bright = _mix(self._color, "#FFFFFF", 0.28)
            try:
                # Halo leger (anti-alias approx)
                c.create_arc(
                    x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5,
                    start=90, extent=extent,
                    style=tk.ARC, outline=soft, width=self._thickness + 1.2,
                )
                c.create_arc(
                    x0, y0, x1, y1,
                    start=90, extent=extent,
                    style=tk.ARC, outline=self._color, width=self._thickness,
                )
                c.create_arc(
                    x0 + 0.4, y0 + 0.4, x1 - 0.4, y1 - 0.4,
                    start=90, extent=extent,
                    style=tk.ARC, outline=bright, width=max(1.0, self._thickness - 1.0),
                )
            except Exception:
                pass
        mid = s / 2
        # Valeur large blanche + unite grise
        c.create_text(
            mid, mid - (6 if self._unit else 0),
            text=self._text, fill="#FFFFFF",
            font=(theme.FONT_UI, 11, "bold"),
        )
        if self._unit:
            c.create_text(
                mid, mid + 11,
                text=self._unit, fill=theme.TEXT_MUTED,
                font=(theme.FONT_MONO, 7),
            )


class SparklineCanvas(ctk.CTkFrame):
    """Area chart horizontal (remplissage + trait) — style Metrics."""

    def __init__(
        self,
        master,
        height: int = 42,
        max_points: int = 60,
        color: str | None = None,
        ymax: float = 100.0,
        **kw,
    ):
        bg = kw.pop("fg_color", CARD_INNER)
        super().__init__(master, fg_color=bg, corner_radius=CORNER_SQ, **kw)
        self._vals: list[float] = []
        self._max_points = max(12, int(max_points))
        self._ymax = max(1.0, float(ymax))
        self._color = color or theme.ACCENT
        self._bg = bg if isinstance(bg, str) else CARD_INNER
        self.canvas = tk.Canvas(
            self, height=height, bg=self._bg, highlightthickness=0, bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redraw())

    def set_color(self, color: str):
        self._color = color
        self._redraw()

    def set_max_points(self, n: int):
        self._max_points = max(12, int(n))
        if len(self._vals) > self._max_points:
            self._vals = self._vals[-self._max_points :]

    def set_ymax(self, ymax: float):
        self._ymax = max(1.0, float(ymax))

    def push(self, value: float | None):
        if value is None:
            return
        self._vals.append(float(value))
        if len(self._vals) > self._max_points:
            if len(self._vals) > self._max_points + 8:
                self._vals = self._vals[::2][-self._max_points :]
            else:
                self._vals = self._vals[-self._max_points :]
        self._redraw()

    def clear(self):
        self._vals.clear()
        self.canvas.delete("all")

    def _fill_hex(self) -> str:
        try:
            return _mix(self._bg, self._color, 0.42)
        except Exception:
            return self._color

    def _redraw(self):
        c = self.canvas
        try:
            w = max(20, int(c.winfo_width()))
            h = max(16, int(c.winfo_height()))
        except Exception:
            return
        c.delete("all")
        # Fond zone graphe
        c.create_rectangle(0, 0, w, h, fill=self._bg, outline="")
        if len(self._vals) < 2:
            return
        ymax = max(self._ymax, max(self._vals) * 1.08, 1.0)
        pad = 1
        n = len(self._vals)
        pts: list[float] = []
        usable_w = w - 2 * pad
        usable_h = h - 2 * pad
        for i, v in enumerate(self._vals):
            x = pad + (usable_w * i / (n - 1))
            y = pad + usable_h * (1.0 - min(1.0, max(0.0, v / ymax)))
            pts.extend([x, y])
        fill_pts = list(pts) + [w - pad, h - pad, pad, h - pad]
        try:
            c.create_polygon(fill_pts, fill=self._fill_hex(), outline="", smooth=True)
        except Exception:
            try:
                c.create_polygon(fill_pts, fill=self._fill_hex(), outline="")
            except Exception:
                pass
        try:
            c.create_line(
                *pts, fill=self._color, width=1.6,
                smooth=True if n >= 4 else False,
            )
        except Exception:
            pass


class MetricRow(ctk.CTkFrame):
    """Ligne Adrenalin : label + [+] | jauge anneau | sparkline area."""

    def __init__(
        self,
        master,
        label: str,
        color: str | None = None,
        unit: str = "%",
        ymax: float = 100.0,
        max_points: int = 60,
        **kw,
    ):
        super().__init__(master, fg_color="transparent", **kw)
        self._unit = unit
        self._ymax = ymax
        color = color or theme.ACCENT

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(
            top, text=label, font=mono(8), text_color="#888888",
        ).pack(side="left")
        ctk.CTkLabel(
            top, text="+", font=mono(10, True), text_color="#666666",
            width=14,
        ).pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", pady=(3, 6))
        self.gauge = RingGauge(body, size=56, thickness=2.5, color=color, bg=CARD_BG)
        self.gauge.pack(side="left", padx=(0, 10))
        self.spark = SparklineCanvas(
            body, height=46, max_points=max_points, color=color, ymax=ymax,
            fg_color=CARD_INNER,
        )
        self.spark.pack(side="left", fill="both", expand=True)

    def update_metric(self, value: float | None, *, text: str | None = None, unit: str | None = None):
        u = unit if unit is not None else self._unit
        if value is None:
            self.gauge.set_value(None)
            return
        disp = text if text is not None else f"{value:.0f}"
        self.gauge.set_value(value, text=disp, unit=u, vmax=self._ymax)
        self.spark.push(value)

    def set_max_points(self, n: int):
        self.spark.set_max_points(n)


class MetricCard(ctk.CTkFrame):
    """Carte carree dense : titre + lignes de mesures (coins 0, hairline)."""

    def __init__(self, master, title: str, **kw):
        super().__init__(
            master,
            fg_color=CARD_BG,
            corner_radius=CORNER_SQ,
            border_width=1,
            border_color=CARD_LINE,
            **kw,
        )
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 2))
        self.title_lbl = ctk.CTkLabel(
            head, text=title, font=mono(9, True), text_color="#FFFFFF",
        )
        self.title_lbl.pack(side="left")
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.rows: dict[str, MetricRow] = {}

    def set_title(self, title: str):
        self.title_lbl.configure(text=title)

    def add_row(
        self,
        key: str,
        label: str,
        color: str | None = None,
        unit: str = "%",
        ymax: float = 100.0,
        max_points: int = 60,
    ) -> MetricRow:
        row = MetricRow(
            self._body, label=label, color=color, unit=unit,
            ymax=ymax, max_points=max_points,
        )
        row.pack(fill="x", pady=1)
        self.rows[key] = row
        return row

    def set_max_points(self, n: int):
        for r in self.rows.values():
            r.set_max_points(n)


class SuiviSidebar(ctk.CTkFrame):
    """Colonne droite Suivi / Superposition (style Adrenalin)."""

    def __init__(
        self,
        master,
        toggles: list[tuple[str, ctk.BooleanVar, str]],
        hz_var: ctk.DoubleVar,
        on_change=None,
        **kw,
    ):
        super().__init__(
            master,
            fg_color=CARD_BG,
            corner_radius=CORNER_SQ,
            border_width=1,
            border_color=CARD_LINE,
            width=128,
            **kw,
        )
        self.pack_propagate(False)
        self._on_change = on_change

        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(
            pad, text="Suivi", font=mono(11, True), text_color="#FFFFFF",
        ).pack(anchor="w")
        ctk.CTkLabel(
            pad, text="Superposition", font=mono(8), text_color="#888888",
        ).pack(anchor="w", pady=(0, 8))

        self.log_btn = ctk.CTkButton(
            pad, text="Journalisation", font=mono(8, True), height=28,
            corner_radius=CORNER_SQ, fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_SOFT, text_color="#0A0A0A",
            command=self._toggle_log,
        )
        self.log_btn.pack(fill="x", pady=(0, 10))
        self._logging = False

        ctk.CTkLabel(
            pad, text="Intervalle (Hz)", font=mono(7), text_color="#888888",
        ).pack(anchor="w")
        row_hz = ctk.CTkFrame(pad, fg_color="transparent")
        row_hz.pack(fill="x", pady=(2, 8))
        self._hz_val = ctk.CTkLabel(
            row_hz, text=f"{hz_var.get():.1f}", font=mono(8, True),
            text_color="#FFFFFF", width=28,
        )
        self._hz_val.pack(side="right")
        self._hz_slider = ctk.CTkSlider(
            row_hz, from_=0.5, to=4.0, variable=hz_var, height=12,
            number_of_steps=35, progress_color=theme.ACCENT,
            button_color="#FFFFFF", button_hover_color=theme.ACCENT_SOFT,
            command=self._on_hz,
        )
        self._hz_slider.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ctk.CTkLabel(
            pad, text="Mesures", font=mono(8, True), text_color="#AAAAAA",
        ).pack(anchor="w", pady=(4, 4))

        self._eyes: dict[str, ctk.CTkLabel] = {}
        for key, var, label in toggles:
            line = ctk.CTkFrame(pad, fg_color="transparent", height=22)
            line.pack(fill="x", pady=1)
            line.pack_propagate(False)
            ctk.CTkLabel(
                line, text=label, font=mono(8), text_color="#CCCCCC",
            ).pack(side="left")
            eye = ctk.CTkLabel(
                line, text="◉" if var.get() else "○",
                font=mono(9), text_color=theme.ACCENT if var.get() else "#555555",
                cursor="hand2",
            )
            eye.pack(side="right")
            eye.bind("<Button-1>", lambda _e, v=var, k=key: self._flip(v, k))
            self._eyes[key] = eye
            # Separateur hairline
            sep = ctk.CTkFrame(pad, fg_color=CARD_LINE, height=1)
            sep.pack(fill="x", pady=(2, 0))

    def _on_hz(self, _v=None):
        try:
            self._hz_val.configure(text=f"{self._hz_slider.get():.1f}")
        except Exception:
            pass
        if self._on_change:
            self._on_change()

    def _flip(self, var: ctk.BooleanVar, key: str):
        var.set(not var.get())
        eye = self._eyes.get(key)
        if eye:
            on = bool(var.get())
            eye.configure(
                text="◉" if on else "○",
                text_color=theme.ACCENT if on else "#555555",
            )
        if self._on_change:
            self._on_change()

    def _toggle_log(self):
        self._logging = not self._logging
        if self._logging:
            self.log_btn.configure(text="Arrêter journal", fg_color=theme.ACCENT_DANGER)
        else:
            self.log_btn.configure(text="Journalisation", fg_color=theme.ACCENT)

    def sync_eyes(self, toggles: list[tuple[str, ctk.BooleanVar, str]]):
        for key, var, _label in toggles:
            eye = self._eyes.get(key)
            if not eye:
                continue
            on = bool(var.get())
            eye.configure(
                text="◉" if on else "○",
                text_color=theme.ACCENT if on else "#555555",
            )
