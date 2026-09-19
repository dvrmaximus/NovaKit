"""Noyau neural ASTAT — orb cinématique."""

from __future__ import annotations

import math
import random
import tkinter as tk

from ui.hud_theme import (
    ACCENT, ACCENT_DIM, ACCENT_GLOW, ACCENT_HOT, ACCENT_SOFT,
    BG_DEEP, LINE, LINE_BRIGHT, SUCCESS,
)


class HudCanvas(tk.Canvas):
    """Orb : grille hex, radar, anneaux, particules, onde vocale."""

    def __init__(self, master, size=260, bg=None, **kwargs):
        super().__init__(
            master, width=size, height=size,
            bg=bg or BG_DEEP, highlightthickness=0, bd=0, **kwargs,
        )
        self.size = size
        self.cx = size // 2
        self.cy = size // 2
        self.phase = 0.0
        self.ring_phase = 0.0
        self.scan_angle = 0.0
        self.state = "idle"
        self.wave_heights = [0.15] * 16
        self.pulse_rings = []  # ripples on state change
        self._last_state = "idle"
        self.particles = [
            {
                "angle": random.uniform(0, math.tau),
                "dist": random.uniform(48, 105),
                "speed": random.uniform(0.008, 0.035) * random.choice([-1, 1]),
                "size": random.uniform(1.2, 2.8),
                "bright": random.random(),
            }
            for _ in range(36)
        ]
        self.ticks = [
            {"angle": i * (math.tau / 48), "len": 4 if i % 4 else 9}
            for i in range(48)
        ]
        self._animer()

    def set_state(self, state: str):
        if state != self.state:
            self.pulse_rings.append({"r": 20, "alpha": 1.0})
        self.state = state

    def _animer(self):
        self.delete("all")
        self._fond_radial()
        self._dessiner_hex_grille()
        self._dessiner_ticks()
        self._dessiner_radar()
        self._dessiner_particules()
        self._dessiner_anneaux()
        self._dessiner_ripples()
        self._dessiner_noyau()
        self._dessiner_croix()
        if self.state in ("listening", "speaking", "thinking"):
            self._dessiner_onde()
        self._dessiner_coins()
        self._dessiner_label()

        boost = {"idle": 1.0, "listening": 2.2, "speaking": 2.6, "thinking": 1.8}.get(self.state, 1.0)
        self.phase += 0.05 * boost
        self.ring_phase += 0.02 * boost
        self.scan_angle = (self.scan_angle + 2.4 * boost) % 360
        self.after(33, self._animer)  # ~30 fps

    def _fond_radial(self):
        # Cercles concentriques très sombres
        for i, r in enumerate((118, 96, 74, 52)):
            col = LINE if i % 2 == 0 else LINE_BRIGHT
            self.create_oval(
                self.cx - r, self.cy - r, self.cx + r, self.cy + r,
                outline=col, width=1,
            )

    def _dessiner_hex_grille(self):
        # Petits hex autour du centre
        r0 = 38
        for ring in range(1, 4):
            rad = r0 + ring * 22
            n = 6 * ring
            for i in range(n):
                a = i * math.tau / n + self.ring_phase * 0.15
                x = self.cx + math.cos(a) * rad
                y = self.cy + math.sin(a) * rad
                s = 3
                self.create_oval(x - s, y - s, x + s, y + s, outline=ACCENT_GLOW, width=1)

    def _dessiner_ticks(self):
        outer = 112
        for t in self.ticks:
            a = t["angle"] + self.ring_phase * 0.01
            c, s = math.cos(a), math.sin(a)
            x1 = self.cx + c * (outer - t["len"])
            y1 = self.cy + s * (outer - t["len"])
            x2 = self.cx + c * outer
            y2 = self.cy + s * outer
            self.create_line(x1, y1, x2, y2, fill=ACCENT_DIM, width=1)

    def _dessiner_radar(self):
        # Balayage radar
        r = 108
        a = math.radians(self.scan_angle)
        x2 = self.cx + math.cos(a) * r
        y2 = self.cy + math.sin(a) * r
        self.create_line(self.cx, self.cy, x2, y2, fill=ACCENT_SOFT, width=2)
        # Cône fantôme
        for i in range(1, 8):
            aa = math.radians(self.scan_angle - i * 4)
            xx = self.cx + math.cos(aa) * r
            yy = self.cy + math.sin(aa) * r
            self.create_line(self.cx, self.cy, xx, yy, fill=ACCENT_GLOW, width=1)

    def _dessiner_particules(self):
        for p in self.particles:
            p["angle"] += p["speed"]
            # oscillation orbitale
            dist = p["dist"] + 3 * math.sin(self.phase + p["bright"] * 6)
            x = self.cx + math.cos(p["angle"]) * dist
            y = self.cy + math.sin(p["angle"]) * dist
            s = p["size"]
            bright = (math.sin(self.phase * 2 + p["bright"] * 10) + 1) / 2
            col = ACCENT_SOFT if bright > 0.55 else ACCENT_DIM
            if self.state == "speaking":
                col = ACCENT_HOT if bright > 0.4 else ACCENT
            self.create_oval(x - s, y - s, x + s, y + s, fill=col, outline="")

    def _dessiner_anneaux(self):
        specs = [
            (102, 1, 1, 130, ACCENT_DIM),
            (86, 2, -1, 100, ACCENT),
            (68, 1, 1, 80, ACCENT_SOFT),
            (48, 2, -1, 60, ACCENT_DIM),
        ]
        for i, (rayon, epaisseur, sens, extent, col) in enumerate(specs):
            start = (self.ring_phase * sens * 55 + i * 40) % 360
            self.create_arc(
                self.cx - rayon, self.cy - rayon, self.cx + rayon, self.cy + rayon,
                start=start, extent=extent, style="arc", outline=col, width=epaisseur,
            )
            self.create_arc(
                self.cx - rayon, self.cy - rayon, self.cx + rayon, self.cy + rayon,
                start=start + 180, extent=extent * 0.55, style="arc",
                outline=ACCENT_GLOW, width=1,
            )

    def _dessiner_ripples(self):
        alive = []
        for rip in self.pulse_rings:
            rip["r"] += 3.5
            rip["alpha"] -= 0.035
            if rip["alpha"] <= 0:
                continue
            r = rip["r"]
            self.create_oval(
                self.cx - r, self.cy - r, self.cx + r, self.cy + r,
                outline=ACCENT_SOFT, width=1,
            )
            alive.append(rip)
        self.pulse_rings = alive

    def _dessiner_noyau(self):
        if self.state == "listening":
            base, amp, layers = 28, 9, [
                (34, ACCENT_GLOW), (20, ACCENT_DIM), (10, ACCENT_SOFT), (0, "#FFFFFF"),
            ]
        elif self.state == "speaking":
            base, amp, layers = 30, 12, [
                (38, "#004A40"), (22, ACCENT_HOT), (10, ACCENT), (0, "#FFFFFF"),
            ]
        elif self.state == "thinking":
            base, amp, layers = 26, 6, [
                (30, ACCENT_GLOW), (16, ACCENT_DIM), (8, ACCENT), (0, ACCENT_SOFT),
            ]
        else:
            base, amp, layers = 24, 4, [
                (28, ACCENT_GLOW), (14, ACCENT_DIM), (6, ACCENT_SOFT), (0, "#DFFFFF"),
            ]

        r = base + amp * math.sin(self.phase)
        for expand, color in layers:
            self.create_oval(
                self.cx - r - expand, self.cy - r - expand,
                self.cx + r + expand, self.cy + r + expand,
                fill=color, outline="",
            )

    def _dessiner_croix(self):
        g = 10
        self.create_line(self.cx - g, self.cy, self.cx + g, self.cy, fill="#FFFFFF", width=1)
        self.create_line(self.cx, self.cy - g, self.cx, self.cy + g, fill="#FFFFFF", width=1)

    def _dessiner_onde(self):
        n = 16
        bw, gap = 4, 3
        total_w = n * (bw + gap)
        start_x = self.cx - total_w // 2
        base_y = self.size - 22
        for i in range(n):
            if self.state == "speaking":
                target = random.uniform(0.35, 1.0)
            elif self.state == "listening":
                target = random.uniform(0.2, 0.75)
            else:
                target = 0.15 + 0.25 * abs(math.sin(self.phase + i * 0.4))
            self.wave_heights[i] += (target - self.wave_heights[i]) * 0.4
            h = int(self.wave_heights[i] * 22)
            x = start_x + i * (bw + gap)
            col = ACCENT_HOT if self.state == "speaking" else ACCENT_SOFT
            self.create_rectangle(x, base_y - h, x + bw, base_y, fill=col, outline="")

    def _dessiner_coins(self):
        m, L = 10, 22
        corners = [
            (m, m, 1, 1), (self.size - m, m, -1, 1),
            (m, self.size - m, 1, -1), (self.size - m, self.size - m, -1, -1),
        ]
        for x, y, dx, dy in corners:
            self.create_line(x, y, x + L * dx, y, fill=ACCENT, width=2)
            self.create_line(x, y, x, y + L * dy, fill=ACCENT, width=2)

    def _dessiner_label(self):
        labels = {
            "idle": "STANDBY",
            "listening": "LISTENING",
            "speaking": "TRANSMIT",
            "thinking": "PROCESSING",
        }
        txt = labels.get(self.state, "STANDBY")
        self.create_text(
            self.cx, 16, text=txt, fill=ACCENT_SOFT,
            font=("Consolas", 8, "bold"),
        )
