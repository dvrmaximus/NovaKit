"""Chrome commun type panneau de controle (style Adrenalin) pour les modes."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

import customtkinter as ctk

import ui.hud_theme as theme
from ui.hud_widgets import mono


class LiveGraph(ctk.CTkFrame):
    """Sparkline leger (Canvas) — historique downsampled, redraw ~1–2 Hz."""

    def __init__(
        self,
        master,
        title: str = "",
        unit: str = "%",
        ymax: float = 100.0,
        max_points: int = 60,
        height: int = 88,
        **kw,
    ):
        super().__init__(master, fg_color=theme.BG_PANEL2, corner_radius=8, **kw)
        self._unit = unit
        self._ymax = max(1.0, float(ymax))
        self._max_points = max(12, int(max_points))
        self._vals: list[float] = []
        self._last_draw = -1.0

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 0))
        self.title_lbl = ctk.CTkLabel(
            head, text=title, font=mono(10, True), text_color=theme.TEXT_SECONDARY,
        )
        self.title_lbl.pack(side="left")
        self.value_lbl = ctk.CTkLabel(
            head, text=f"— {unit}", font=mono(12, True), text_color=theme.TEXT_PRIMARY,
        )
        self.value_lbl.pack(side="right")

        self.canvas = tk.Canvas(
            self,
            height=height,
            bg=theme.BG_PANEL2,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", padx=8, pady=(4, 8))
        self.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Configure>", lambda e: self._redraw())

    def set_max_points(self, n: int):
        self._max_points = max(12, int(n))
        if len(self._vals) > self._max_points:
            self._vals = self._vals[-self._max_points :]

    def push(self, value: float | None, alert: bool = False):
        if value is None:
            self.value_lbl.configure(text=f"n/d {self._unit}", text_color=theme.TEXT_MUTED)
            return
        v = float(value)
        self._vals.append(v)
        if len(self._vals) > self._max_points:
            # downsample : garde 1 sur 2 des plus anciens si overflow fort
            if len(self._vals) > self._max_points + 10:
                self._vals = self._vals[::2][-self._max_points :]
            else:
                self._vals = self._vals[-self._max_points :]
        color = theme.ACCENT_DANGER if alert else theme.TEXT_PRIMARY
        if self._unit == "%":
            self.value_lbl.configure(text=f"{v:.0f} {self._unit}", text_color=color)
        elif self._unit == "ms":
            self.value_lbl.configure(text=f"{v:.1f} {self._unit}", text_color=color)
        else:
            self.value_lbl.configure(text=f"{v:.0f} {self._unit}", text_color=color)
        self._redraw()

    def clear(self):
        self._vals.clear()
        self.canvas.delete("all")
        self.value_lbl.configure(text=f"— {self._unit}", text_color=theme.TEXT_MUTED)

    def _redraw(self):
        c = self.canvas
        try:
            w = max(40, int(c.winfo_width()))
            h = max(40, int(c.winfo_height()))
        except Exception:
            return
        c.delete("all")
        pad = 4
        c.create_line(pad, h - pad, w - pad, h - pad, fill=theme.LINE, width=1)
        c.create_line(pad, pad, pad, h - pad, fill=theme.LINE, width=1)
        if len(self._vals) < 2:
            return
        ymax = max(self._ymax, max(self._vals) * 1.05, 1.0)
        n = len(self._vals)
        pts = []
        usable_w = w - 2 * pad
        usable_h = h - 2 * pad
        for i, v in enumerate(self._vals):
            x = pad + (usable_w * i / (n - 1))
            y = pad + usable_h * (1.0 - min(1.0, max(0.0, v / ymax)))
            pts.extend([x, y])
        accent = theme.ACCENT
        # zone sous la courbe
        fill_pts = list(pts) + [w - pad, h - pad, pad, h - pad]
        try:
            c.create_polygon(fill_pts, fill=theme.ACCENT_GLOW, outline="")
        except Exception:
            pass
        c.create_line(*pts, fill=accent, width=2, smooth=True)


class ModeShell(ctk.CTkToplevel):
    """Fenetre panneau : barre titre + sidebar gauche + pages."""

    def __init__(
        self,
        master,
        title: str,
        subtitle: str,
        nav: list[tuple[str, str]],
        width: int = 960,
        height: int = 640,
        on_close: Callable | None = None,
        **kw,
    ):
        super().__init__(master, **kw)
        self._on_close = on_close
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._current = ""

        self.title(title)
        self.configure(fg_color=theme.BG_MAIN)
        ctk.set_appearance_mode("dark")
        try:
            from ui.win_desktop import fit_toplevel
            fit_toplevel(self, width, height)
        except Exception:
            self.geometry(f"{width}x{height}")
            self.minsize(720, 480)

        # —— Header ——
        head = ctk.CTkFrame(self, fg_color=theme.BG_DEEP, height=56, corner_radius=0)
        head.pack(fill="x")
        head.pack_propagate(False)
        accent_bar = ctk.CTkFrame(head, fg_color=theme.ACCENT, width=4, corner_radius=0)
        accent_bar.pack(side="left", fill="y")
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left", fill="y", padx=14)
        ctk.CTkLabel(
            titles, text=title, font=mono(15, True), text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(10, 0))
        ctk.CTkLabel(
            titles, text=subtitle, font=mono(9), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")
        self.status_lbl = ctk.CTkLabel(
            head, text="", font=mono(9), text_color=theme.TEXT_MUTED,
        )
        self.status_lbl.pack(side="right", padx=16)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        self.sidebar = ctk.CTkFrame(body, fg_color=theme.BG_PANEL, width=168, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(
            self.sidebar, text="NAVIGATION", font=mono(8, True), text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(16, 8))

        self.content = ctk.CTkFrame(body, fg_color=theme.BG_MAIN, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        for key, label in nav:
            page = ctk.CTkFrame(self.content, fg_color="transparent")
            self._pages[key] = page
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                font=mono(11),
                height=36,
                corner_radius=6,
                anchor="w",
                fg_color="transparent",
                hover_color=theme.ACCENT_DIM,
                text_color=theme.TEXT_SECONDARY,
                border_width=0,
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[key] = btn

        self.bind("<Escape>", lambda e: self._fermer())
        self.protocol("WM_DELETE_WINDOW", self._fermer)
        self.after(40, self.focus_force)
        if nav:
            self.show_page(nav[0][0])
        self.apply_window_prefs()

    def page(self, key: str) -> ctk.CTkFrame:
        return self._pages[key]

    def show_page(self, key: str):
        if key not in self._pages:
            return
        for k, fr in self._pages.items():
            if k == key:
                fr.pack(fill="both", expand=True, padx=16, pady=14)
            else:
                fr.pack_forget()
        self._current = key
        for k, b in self._nav_btns.items():
            if k == key:
                b.configure(
                    fg_color=theme.ACCENT_DIM,
                    text_color=theme.TEXT_PRIMARY,
                    border_width=1,
                    border_color=theme.GLASS_BORDER_HOT,
                )
            else:
                b.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT_SECONDARY,
                    border_width=0,
                )

    def set_status(self, text: str):
        try:
            self.status_lbl.configure(text=text)
        except Exception:
            pass

    def apply_window_prefs(self):
        try:
            from core.mode_settings import get_section
            gl = get_section("global")
            self.attributes("-topmost", bool(gl.get("always_on_top")))
            self.attributes("-alpha", float(gl.get("opacity", 0.96)))
        except Exception:
            pass

    def lift_focus(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.apply_window_prefs()
        except Exception:
            pass

    def _fermer(self):
        cb = self._on_close
        try:
            self.destroy()
        except Exception:
            pass
        if cb:
            try:
                cb()
            except Exception:
                pass


def labeled_switch(parent, text: str, var: ctk.BooleanVar, command=None) -> ctk.CTkFrame:
    row = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkLabel(row, text=text, font=mono(11), text_color=theme.TEXT_SECONDARY).pack(
        side="left",
    )
    sw = ctk.CTkSwitch(
        row,
        text="",
        variable=var,
        width=42,
        progress_color=theme.ACCENT,
        button_color=theme.TEXT_PRIMARY,
        button_hover_color=theme.ACCENT_SOFT,
        command=command,
    )
    sw.pack(side="right")
    return row


def labeled_slider(
    parent,
    text: str,
    var: ctk.DoubleVar | ctk.IntVar,
    from_: float,
    to: float,
    command=None,
    fmt: str = "{:.1f}",
) -> tuple[ctk.CTkFrame, ctk.CTkLabel]:
    box = ctk.CTkFrame(parent, fg_color="transparent")
    top = ctk.CTkFrame(box, fg_color="transparent")
    top.pack(fill="x")
    ctk.CTkLabel(top, text=text, font=mono(11), text_color=theme.TEXT_SECONDARY).pack(side="left")
    val_lbl = ctk.CTkLabel(top, text="", font=mono(10, True), text_color=theme.ACCENT_SOFT)
    val_lbl.pack(side="right")

    def _upd(_=None):
        try:
            val_lbl.configure(text=fmt.format(var.get()))
        except Exception:
            val_lbl.configure(text=str(var.get()))
        if command:
            command()

    slider = ctk.CTkSlider(
        box,
        from_=from_,
        to=to,
        variable=var,
        number_of_steps=max(1, int((to - from_) * 10) if isinstance(var, ctk.DoubleVar) else int(to - from_)),
        progress_color=theme.ACCENT,
        button_color=theme.ACCENT_SOFT,
        button_hover_color=theme.ACCENT_HOT,
        command=lambda _v: _upd(),
    )
    slider.pack(fill="x", pady=(4, 0))
    _upd()
    return box, val_lbl
