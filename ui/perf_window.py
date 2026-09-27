"""Vue Performance embarquee dans Astat (graphes, capteurs, reglages)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import ui.hud_theme as theme
from core import mode_settings
from core.perf_monitor import format_net, snapshot
from ui.hud_widgets import MeterBar, SectionTitle, mono
from ui.mode_shell import CORNER, HudModePanel, LiveGraph, labeled_slider, labeled_switch


class PerfPanel(HudModePanel):
    """Contenu Performance — vit dans le panneau gauche du HUD."""

    def __init__(self, master, wraplength: int = 340, **kw):
        self._wrap = wraplength
        self._tick_id = None
        self._active = False
        self._cfg = mode_settings.get_section("perf")
        super().__init__(
            master,
            title="Performance",
            nav=[
                ("overview", "Resume"),
                ("graphs", "Graphes"),
                ("sensors", "Capteurs"),
                ("settings", "Reglages"),
            ],
            **kw,
        )
        self._build_overview()
        self._build_graphs()
        self._build_sensors()
        self._build_settings()

    def set_active(self, active: bool):
        self._active = bool(active)
        if self._active:
            self._schedule_tick()
        else:
            self._stop_tick()

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _schedule_tick(self):
        self._stop_tick()
        if not self._active:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self._refresh()
        hz = float(self._cfg.get("refresh_hz", 1.5) or 1.5)
        delay = max(250, int(1000 / max(0.5, hz)))
        self._tick_id = self.after(delay, self._schedule_tick)

    def _build_overview(self):
        page = self.page("overview")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        SectionTitle(scroll, "Resume systeme").pack(fill="x", pady=(0, 6))
        self.m_cpu = MeterBar(scroll, "CPU")
        self.m_cpu.pack(fill="x", pady=2)
        self.m_ram = MeterBar(scroll, "RAM")
        self.m_ram.pack(fill="x", pady=2)
        self.m_gpu = MeterBar(scroll, "GPU")
        self.m_gpu.pack(fill="x", pady=2)
        self.m_vram = MeterBar(scroll, "VRAM")
        self.m_vram.pack(fill="x", pady=2)
        self.m_disk = MeterBar(scroll, "Disque")
        self.m_disk.pack(fill="x", pady=2)

        self.ov_detail = ctk.CTkLabel(
            scroll, text="", font=mono(9), text_color=theme.TEXT_SECONDARY,
            justify="left", wraplength=self._wrap,
        )
        self.ov_detail.pack(anchor="w", pady=(10, 0))
        self.ov_alerts = ctk.CTkLabel(
            scroll, text="", font=mono(9, True), text_color=theme.ACCENT_WARN,
            justify="left", wraplength=self._wrap,
        )
        self.ov_alerts.pack(anchor="w", pady=(6, 0))

    def _build_graphs(self):
        page = self.page("graphs")
        pts = int(self._cfg.get("history_points", 60))
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        self.g_cpu = LiveGraph(scroll, title="CPU", unit="%", max_points=pts, height=72)
        self.g_cpu.pack(fill="x", pady=3)
        self.g_ram = LiveGraph(scroll, title="RAM", unit="%", max_points=pts, height=72)
        self.g_ram.pack(fill="x", pady=3)
        self.g_gpu = LiveGraph(scroll, title="GPU", unit="%", max_points=pts, height=72)
        self.g_gpu.pack(fill="x", pady=3)
        self.g_net = LiveGraph(scroll, title="Reseau ↓", unit="Ko/s", ymax=500, max_points=pts, height=72)
        self.g_net.pack(fill="x", pady=3)

    def _build_sensors(self):
        page = self.page("sensors")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Capteurs").pack(fill="x", pady=(0, 6))
        self.sensor_lbls: dict[str, ctk.CTkLabel] = {}
        for key, label in (
            ("cpu", "Processeur"),
            ("ram", "Memoire"),
            ("disk", "Stockage"),
            ("gpu", "Carte graphique"),
            ("temps", "Temperatures"),
            ("net", "Reseau"),
        ):
            card = ctk.CTkFrame(
                scroll, fg_color=theme.BG_PANEL2, corner_radius=CORNER,
                border_width=1, border_color=theme.LINE,
            )
            card.pack(fill="x", pady=3)
            ctk.CTkLabel(
                card, text=label, font=mono(9, True), text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=10, pady=(6, 0))
            lbl = ctk.CTkLabel(
                card, text="—", font=mono(9), text_color=theme.TEXT_SECONDARY,
                justify="left", wraplength=self._wrap,
            )
            lbl.pack(anchor="w", padx=10, pady=(2, 8))
            self.sensor_lbls[key] = lbl

    def _build_settings(self):
        page = self.page("settings")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Affichage").pack(fill="x", pady=(0, 6))

        self.v_show_cpu = ctk.BooleanVar(value=bool(self._cfg.get("show_cpu", True)))
        self.v_show_ram = ctk.BooleanVar(value=bool(self._cfg.get("show_ram", True)))
        self.v_show_gpu = ctk.BooleanVar(value=bool(self._cfg.get("show_gpu", True)))
        self.v_show_disk = ctk.BooleanVar(value=bool(self._cfg.get("show_disk", True)))
        self.v_show_net = ctk.BooleanVar(value=bool(self._cfg.get("show_net", True)))
        self.v_show_temps = ctk.BooleanVar(value=bool(self._cfg.get("show_temps", True)))
        for var, txt in (
            (self.v_show_cpu, "CPU"),
            (self.v_show_ram, "RAM"),
            (self.v_show_gpu, "GPU / VRAM"),
            (self.v_show_disk, "Disque"),
            (self.v_show_net, "Reseau"),
            (self.v_show_temps, "Temperatures"),
        ):
            labeled_switch(scroll, txt, var, command=self._persist_settings).pack(fill="x", pady=2)

        SectionTitle(scroll, "Rafraichissement & alertes").pack(fill="x", pady=(12, 6))
        self.v_hz = ctk.DoubleVar(value=float(self._cfg.get("refresh_hz", 1.5)))
        box, _ = labeled_slider(
            scroll, "Frequence (Hz)", self.v_hz, 0.5, 4.0,
            command=self._persist_settings, fmt="{:.1f} Hz",
        )
        box.pack(fill="x", pady=4)

        self.v_alert_cpu = ctk.IntVar(value=int(self._cfg.get("alert_cpu", 90)))
        self.v_alert_ram = ctk.IntVar(value=int(self._cfg.get("alert_ram", 90)))
        self.v_alert_gpu = ctk.IntVar(value=int(self._cfg.get("alert_gpu", 95)))
        for var, txt in (
            (self.v_alert_cpu, "Alerte CPU (%)"),
            (self.v_alert_ram, "Alerte RAM (%)"),
            (self.v_alert_gpu, "Alerte GPU (%)"),
        ):
            box, _ = labeled_slider(
                scroll, txt, var, 50, 100, command=self._persist_settings, fmt="{:.0f} %",
            )
            box.pack(fill="x", pady=4)

        self.v_hist = ctk.IntVar(value=int(self._cfg.get("history_points", 60)))
        box, _ = labeled_slider(
            scroll, "Points graphes", self.v_hist, 20, 120,
            command=self._persist_settings, fmt="{:.0f}",
        )
        box.pack(fill="x", pady=4)

        ctk.CTkButton(
            scroll,
            text="Appliquer",
            font=mono(10, True),
            height=30,
            corner_radius=CORNER,
            fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY,
            command=self._persist_settings,
        ).pack(anchor="w", pady=(10, 0))

    def _persist_settings(self):
        patch = {
            "perf": {
                "refresh_hz": float(self.v_hz.get()),
                "show_cpu": bool(self.v_show_cpu.get()),
                "show_ram": bool(self.v_show_ram.get()),
                "show_gpu": bool(self.v_show_gpu.get()),
                "show_disk": bool(self.v_show_disk.get()),
                "show_net": bool(self.v_show_net.get()),
                "show_temps": bool(self.v_show_temps.get()),
                "alert_cpu": int(self.v_alert_cpu.get()),
                "alert_ram": int(self.v_alert_ram.get()),
                "alert_gpu": int(self.v_alert_gpu.get()),
                "history_points": int(self.v_hist.get()),
            },
        }
        mode_settings.save(patch)
        self._cfg = mode_settings.get_section("perf")
        pts = int(self._cfg.get("history_points", 60))
        for g in (self.g_cpu, self.g_ram, self.g_gpu, self.g_net):
            g.set_max_points(pts)
        self.set_status("ok")
        if self._active:
            self._schedule_tick()

    def update_from_snap(self, snap) -> None:
        """Compat tick HUD externe (resume rapide)."""
        if snap is None:
            return
        try:
            self.m_cpu.set_value(snap.cpu_percent)
            self.m_ram.set_value(snap.ram_percent)
            if snap.gpu_percent is not None:
                self.m_gpu.set_value(snap.gpu_percent)
        except Exception:
            pass

    def _refresh(self):
        try:
            snap = snapshot()
        except Exception:
            return
        cfg = self._cfg
        alerts = []

        if cfg.get("show_cpu", True):
            self.m_cpu.set_value(snap.cpu_percent)
            alert = snap.cpu_percent >= cfg.get("alert_cpu", 90)
            self.g_cpu.push(snap.cpu_percent, alert=alert)
            if alert:
                alerts.append(f"CPU {snap.cpu_percent:.0f}%")
        if cfg.get("show_ram", True):
            self.m_ram.set_value(snap.ram_percent)
            alert = snap.ram_percent >= cfg.get("alert_ram", 90)
            self.g_ram.push(snap.ram_percent, alert=alert)
            if alert:
                alerts.append(f"RAM {snap.ram_percent:.0f}%")
        if cfg.get("show_gpu", True):
            if snap.gpu_percent is not None:
                self.m_gpu.set_value(snap.gpu_percent)
                alert = snap.gpu_percent >= cfg.get("alert_gpu", 95)
                self.g_gpu.push(snap.gpu_percent, alert=alert)
                if alert:
                    alerts.append(f"GPU {snap.gpu_percent:.0f}%")
            else:
                self.m_gpu.set_value(0)
                self.m_gpu.value_lbl.configure(text="n/d", text_color=theme.TEXT_MUTED)
                self.g_gpu.push(None)
            if snap.gpu_vram_percent is not None:
                self.m_vram.set_value(snap.gpu_vram_percent)
            else:
                self.m_vram.set_value(0)
                self.m_vram.value_lbl.configure(text="n/d", text_color=theme.TEXT_MUTED)
        if cfg.get("show_disk", True) and snap.disk_percent is not None:
            self.m_disk.set_value(snap.disk_percent)

        if cfg.get("show_net", True) and snap.net_down_kbps is not None:
            self.g_net.push(snap.net_down_kbps)

        parts = [
            f"CPU {snap.cpu_percent:.0f}% ({snap.cpu_count} thr)",
            f"RAM {snap.ram_used_gb:.1f}/{snap.ram_total_gb:.1f} Go",
        ]
        if snap.disk_percent is not None:
            parts.append(f"Disque {snap.disk_percent:.0f}%")
        if snap.gpu_name:
            parts.append(snap.gpu_name)
        if cfg.get("show_temps", True):
            tparts = []
            if snap.cpu_temp_c is not None:
                tparts.append(f"CPU {snap.cpu_temp_c:.0f}°C")
            if snap.gpu_temp_c is not None:
                tparts.append(f"GPU {snap.gpu_temp_c:.0f}°C")
            if tparts:
                parts.append(" · ".join(tparts))
        if cfg.get("show_net", True):
            parts.append(f"↓ {format_net(snap.net_down_kbps)}  ↑ {format_net(snap.net_up_kbps)}")
        self.ov_detail.configure(text="\n".join(parts))
        self.ov_alerts.configure(
            text=("Alertes : " + ", ".join(alerts)) if alerts else "Aucune alerte.",
            text_color=theme.ACCENT_DANGER if alerts else theme.TEXT_MUTED,
        )

        self.sensor_lbls["cpu"].configure(
            text=f"Charge {snap.cpu_percent:.0f}% — {snap.cpu_count} threads"
        )
        self.sensor_lbls["ram"].configure(
            text=f"{snap.ram_used_gb:.1f} / {snap.ram_total_gb:.1f} Go ({snap.ram_percent:.0f}%)"
        )
        if snap.disk_percent is not None and snap.disk_used_gb is not None:
            self.sensor_lbls["disk"].configure(
                text=f"{snap.disk_used_gb:.0f} / {snap.disk_total_gb:.0f} Go ({snap.disk_percent:.0f}%)"
            )
        else:
            self.sensor_lbls["disk"].configure(text="n/d")
        gpu_txt = snap.gpu_name or "GPU non detecte"
        if snap.gpu_percent is not None:
            gpu_txt += f"\nCharge {snap.gpu_percent:.0f}%"
        if snap.gpu_vram_percent is not None:
            gpu_txt += (
                f"\nVRAM {snap.gpu_vram_used_gb:.1f}/{snap.gpu_vram_total_gb:.1f} Go "
                f"({snap.gpu_vram_percent:.0f}%)"
            )
        self.sensor_lbls["gpu"].configure(text=gpu_txt)
        tparts = []
        if snap.cpu_temp_c is not None:
            tparts.append(f"CPU {snap.cpu_temp_c:.0f} °C")
        if snap.gpu_temp_c is not None:
            tparts.append(f"GPU {snap.gpu_temp_c:.0f} °C")
        self.sensor_lbls["temps"].configure(
            text=" · ".join(tparts) if tparts else "Temperatures indisponibles"
        )
        self.sensor_lbls["net"].configure(
            text=f"↓ {format_net(snap.net_down_kbps)}  ·  ↑ {format_net(snap.net_up_kbps)}"
        )
        self.set_status(f"{cfg.get('refresh_hz', 1.5):.1f} Hz")


# —— Fenetre optionnelle (avance) ——

_PERF_WIN = None


def ouvrir_perf(master, on_close: Callable | None = None):
    """Ouvre une fenetre separee (avance) — UX par defaut = panneau in-HUD."""
    global _PERF_WIN
    from ui.mode_shell import ModeShell

    if _PERF_WIN is not None:
        try:
            if _PERF_WIN.winfo_exists():
                _PERF_WIN.lift_focus()
                return _PERF_WIN
        except Exception:
            _PERF_WIN = None

    class _Win(ModeShell):
        def __init__(self):
            super().__init__(
                master,
                title="Performance (avance)",
                subtitle="Vue detachee — preferer les onglets Astat",
                nav=[("main", "Contenu")],
                width=720,
                height=640,
                on_close=self._on_closed,
            )
            self.panel = PerfPanel(self.page("main"), wraplength=620)
            self.panel.pack(fill="both", expand=True)
            self.panel.set_active(True)

        def _on_closed(self):
            global _PERF_WIN
            try:
                self.panel.set_active(False)
            except Exception:
                pass
            _PERF_WIN = None
            if on_close:
                on_close()

    _PERF_WIN = _Win()
    return _PERF_WIN


def fermer_perf() -> None:
    global _PERF_WIN
    if _PERF_WIN is not None:
        try:
            if _PERF_WIN.winfo_exists():
                _PERF_WIN._fermer()
        except Exception:
            pass
    _PERF_WIN = None
