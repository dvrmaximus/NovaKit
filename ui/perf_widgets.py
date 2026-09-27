"""Widgets style Adrenalin — jauges anneau + sparklines area (Tk Canvas)."""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

import ui.hud_theme as theme
from ui.mode_shell import CORNER


class RingGauge(ctk.CTkFrame):
    """Anneau fin avec valeur centree (style Metrics Adrenalin)."""

    def __init__(
        self,
        master,
        size: int = 56,
        thickness: float = 3.0,
        color: str | None = None,
        **kw,
    ):
        super().__init__(master, fg_color="transparent", width=size + 8, height=size, **kw)
        self.pack_propagate(False)
        self._size = size
        self._thickness = thickness
        self._color = color or theme.ACCENT
        self._pct = 0.0
        self._text = "—"
        self._unit = ""
        self.canvas = tk.Canvas(
            self, width=size, height=size, bg=theme.BG_PANEL2,
            highlightthickness=0, bd=0,
        )
        self.canvas.place(x=0, y=0)
        self._draw()

    def set_colors(self, color: str, bg: str | None = None):
        self._color = color
        if bg:
            try:
                self.canvas.configure(bg=bg)
            except Exception:
                pass
        self._draw()

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
        self._draw()

    def _draw(self):
        c = self.canvas
        c.delete("all")
        s = self._size
        pad = 3
        x0, y0, x1, y1 = pad, pad, s - pad, s - pad
        track = theme.LINE
        try:
            c.create_arc(
                x0, y0, x1, y1,
                start=90, extent=-359.9,
                style=tk.ARC, outline=track, width=self._thickness,
            )
            extent = -max(0.5, min(359.9, self._pct * 3.599))
            if self._pct > 0.5:
                c.create_arc(
                    x0, y0, x1, y1,
                    start=90, extent=extent,
                    style=tk.ARC, outline=self._color, width=self._thickness,
                )
        except Exception:
            pass
        mid = s / 2
        c.create_text(
            mid, mid - (5 if self._unit else 0),
            text=self._text, fill=theme.TEXT_PRIMARY,
            font=(theme.FONT_MONO, 10, "bold"),
        )
        if self._unit:
            c.create_text(
                mid, mid + 10,
                text=self._unit, fill=theme.TEXT_MUTED,
                font=(theme.FONT_MONO, 7),
            )


class SparklineCanvas(ctk.CTkFrame):
    """Area chart horizontal (remplissage + trait)."""

    def __init__(
        self,
        master,
        height: int = 40,
        max_points: int = 60,
        color: str | None = None,
        ymax: float = 100.0,
        **kw,
    ):
        bg = kw.pop("fg_color", theme.BG_PANEL2)
        super().__init__(master, fg_color=bg, corner_radius=0, **kw)
        self._vals: list[float] = []
        self._max_points = max(12, int(max_points))
        self._ymax = max(1.0, float(ymax))
        self._color = color or theme.ACCENT
        self._bg = bg if isinstance(bg, str) else theme.BG_PANEL2
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
        # Assombrir l'accent pour le remplissage
        try:
            from ui.hud_theme import _mix
            return _mix(self._bg, self._color, 0.45)
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
            c.create_polygon(fill_pts, fill=self._fill_hex(), outline="")
        except Exception:
            pass
        try:
            c.create_line(*pts, fill=self._color, width=1.5, smooth=False)
        except Exception:
            pass


class MetricRow(ctk.CTkFrame):
    """Ligne : label + jauge + sparkline."""

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
            top, text=label, font=mono(8), text_color=theme.TEXT_SECONDARY,
        ).pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", pady=(2, 4))
        self.gauge = RingGauge(body, size=52, color=color)
        self.gauge.pack(side="left", padx=(0, 8))
        self.spark = SparklineCanvas(
            body, height=44, max_points=max_points, color=color, ymax=ymax,
            fg_color=theme.BG_PANEL2,
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
    """Carte carree dense : titre + lignes de mesures."""

    def __init__(self, master, title: str, **kw):
        super().__init__(
            master,
            fg_color=theme.BG_PANEL2,
            corner_radius=CORNER,
            border_width=1,
            border_color=theme.LINE,
            **kw,
        )
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 4))
        self.title_lbl = ctk.CTkLabel(
            head, text=title, font=mono(10, True), text_color=theme.TEXT_PRIMARY,
        )
        self.title_lbl.pack(side="left")
        self._body = ctk.CTkFrame(self, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
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
        row.pack(fill="x", pady=2)
        self.rows[key] = row
        return row

    def set_max_points(self, n: int):
        for r in self.rows.values():
            r.set_max_points(n)
