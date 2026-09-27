"""Centre Performance — panneau type Adrenalin (graphes, capteurs, reglages)."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

import ui.hud_theme as theme
from core import mode_settings
from core.perf_monitor import format_net, snapshot
from ui.hud_widgets import MeterBar, SectionTitle, mono
from ui.mode_shell import LiveGraph, ModeShell, labeled_slider, labeled_switch

_PERF_WIN: "PerfWindow | None" = None


class PerfWindow(ModeShell):
    def __init__(self, master, on_close: Callable | None = None):
        super().__init__(
            master,
            title="Centre Performance",
            subtitle="Telemetrie live · NovaKit",
            nav=[
                ("overview", "Vue d'ensemble"),
                ("graphs", "Graphiques"),
                ("sensors", "Capteurs"),
                ("settings", "Reglages"),
            ],
            width=980,
            height=660,
            on_close=self._wrap_close(on_close),
        )
        self._tick_id = None
        self._cfg = mode_settings.get_section("perf")
        self._build_overview()
        self._build_graphs()
        self._build_sensors()
        self._build_settings()
        self._schedule_tick()

    def _wrap_close(self, on_close):
        def _cb():
            global _PERF_WIN
            self._stop_tick()
            _PERF_WIN = None
            if on_close:
                on_close()
        return _cb

    def _stop_tick(self):
        if self._tick_id is not None:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None

    def _schedule_tick(self):
        self._stop_tick()
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

        SectionTitle(scroll, "Resume systeme").pack(fill="x", pady=(0, 8))
        meters = ctk.CTkFrame(scroll, fg_color="transparent")
        meters.pack(fill="x")
        self.m_cpu = MeterBar(meters, "CPU")
        self.m_cpu.pack(fill="x", pady=3)
        self.m_ram = MeterBar(meters, "RAM")
        self.m_ram.pack(fill="x", pady=3)
        self.m_gpu = MeterBar(meters, "GPU")
        self.m_gpu.pack(fill="x", pady=3)
        self.m_vram = MeterBar(meters, "VRAM")
        self.m_vram.pack(fill="x", pady=3)
        self.m_disk = MeterBar(meters, "Disque")
        self.m_disk.pack(fill="x", pady=3)

        self.ov_detail = ctk.CTkLabel(
            scroll, text="", font=mono(10), text_color=theme.TEXT_SECONDARY,
            justify="left", wraplength=700,
        )
        self.ov_detail.pack(anchor="w", pady=(12, 0))
        self.ov_alerts = ctk.CTkLabel(
            scroll, text="", font=mono(10, True), text_color=theme.ACCENT_WARN,
            justify="left", wraplength=700,
        )
        self.ov_alerts.pack(anchor="w", pady=(8, 0))

        tip = ctk.CTkLabel(
            scroll,
            text="Astuce : ouvre aussi le Centre Gaming a cote — fermer ce panneau ne ferme pas le HUD.",
            font=mono(9),
            text_color=theme.TEXT_MUTED,
        )
        tip.pack(anchor="w", pady=(16, 0))

    def _build_graphs(self):
        page = self.page("graphs")
        pts = int(self._cfg.get("history_points", 60))
        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        self.g_cpu = LiveGraph(grid, title="CPU", unit="%", max_points=pts, height=100)
        self.g_cpu.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)
        self.g_ram = LiveGraph(grid, title="RAM", unit="%", max_points=pts, height=100)
        self.g_ram.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)
        self.g_gpu = LiveGraph(grid, title="GPU", unit="%", max_points=pts, height=100)
        self.g_gpu.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=4)
        self.g_net = LiveGraph(grid, title="Reseau ↓", unit="Ko/s", ymax=500, max_points=pts, height=100)
        self.g_net.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=4)

    def _build_sensors(self):
        page = self.page("sensors")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Capteurs detailles").pack(fill="x", pady=(0, 8))
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
                scroll, fg_color=theme.BG_PANEL2, corner_radius=8,
                border_width=1, border_color=theme.LINE,
            )
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(
                card, text=label, font=mono(10, True), text_color=theme.TEXT_PRIMARY,
            ).pack(anchor="w", padx=12, pady=(8, 0))
            lbl = ctk.CTkLabel(
                card, text="—", font=mono(10), text_color=theme.TEXT_SECONDARY,
                justify="left", wraplength=700,
            )
            lbl.pack(anchor="w", padx=12, pady=(2, 10))
            self.sensor_lbls[key] = lbl

    def _build_settings(self):
        page = self.page("settings")
        scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        SectionTitle(scroll, "Affichage des capteurs").pack(fill="x", pady=(0, 8))

        self.v_show_cpu = ctk.BooleanVar(value=bool(self._cfg.get("show_cpu", True)))
        self.v_show_ram = ctk.BooleanVar(value=bool(self._cfg.get("show_ram", True)))
        self.v_show_gpu = ctk.BooleanVar(value=bool(self._cfg.get("show_gpu", True)))
        self.v_show_disk = ctk.BooleanVar(value=bool(self._cfg.get("show_disk", True)))
        self.v_show_net = ctk.BooleanVar(value=bool(self._cfg.get("show_net", True)))
        self.v_show_temps = ctk.BooleanVar(value=bool(self._cfg.get("show_temps", True)))
        for var, txt in (
            (self.v_show_cpu, "Afficher CPU"),
            (self.v_show_ram, "Afficher RAM"),
            (self.v_show_gpu, "Afficher GPU / VRAM"),
            (self.v_show_disk, "Afficher disque"),
            (self.v_show_net, "Afficher reseau"),
            (self.v_show_temps, "Afficher temperatures"),
        ):
            labeled_switch(scroll, txt, var, command=self._persist_settings).pack(fill="x", pady=3)

        SectionTitle(scroll, "Rafraichissement & alertes").pack(fill="x", pady=(16, 8))
        self.v_hz = ctk.DoubleVar(value=float(self._cfg.get("refresh_hz", 1.5)))
        box, _ = labeled_slider(
            scroll, "Frequence metriques (Hz)", self.v_hz, 0.5, 4.0,
            command=self._persist_settings, fmt="{:.1f} Hz",
        )
        box.pack(fill="x", pady=6)

        self.v_alert_cpu = ctk.IntVar(value=int(self._cfg.get("alert_cpu", 90)))
        self.v_alert_ram = ctk.IntVar(value=int(self._cfg.get("alert_ram", 90)))
        self.v_alert_gpu = ctk.IntVar(value=int(self._cfg.get("alert_gpu", 95)))
        for var, txt in (
            (self.v_alert_cpu, "Seuil alerte CPU (%)"),
            (self.v_alert_ram, "Seuil alerte RAM (%)"),
            (self.v_alert_gpu, "Seuil alerte GPU (%)"),
        ):
            box, _ = labeled_slider(
                scroll, txt, var, 50, 100, command=self._persist_settings, fmt="{:.0f} %",
            )
            box.pack(fill="x", pady=6)

        self.v_hist = ctk.IntVar(value=int(self._cfg.get("history_points", 60)))
        box, _ = labeled_slider(
            scroll, "Points d'historique graphes", self.v_hist, 20, 120,
            command=self._persist_settings, fmt="{:.0f}",
        )
        box.pack(fill="x", pady=6)

        SectionTitle(scroll, "Fenetre").pack(fill="x", pady=(16, 8))
        gl = mode_settings.get_section("global")
        self.v_top = ctk.BooleanVar(value=bool(gl.get("always_on_top")))
        self.v_open = ctk.BooleanVar(value=bool(gl.get("open_window_on_mode", True)))
        self.v_opacity = ctk.DoubleVar(value=float(gl.get("opacity", 0.96)))
        labeled_switch(scroll, "Toujours au premier plan", self.v_top, command=self._persist_settings).pack(
            fill="x", pady=3,
        )
        labeled_switch(
            scroll, "Ouvrir ce panneau au passage en mode Performance", self.v_open,
            command=self._persist_settings,
        ).pack(fill="x", pady=3)
        box, _ = labeled_slider(
            scroll, "Opacite panneau", self.v_opacity, 0.55, 1.0,
            command=self._persist_settings, fmt="{:.0%}",
        )
        box.pack(fill="x", pady=6)

        ctk.CTkButton(
            scroll,
            text="Appliquer maintenant",
            font=mono(11, True),
            height=34,
            fg_color=theme.ACCENT_DIM,
            hover_color=theme.GLASS_BORDER_HOT,
            text_color=theme.TEXT_PRIMARY,
            command=self._persist_settings,
        ).pack(anchor="w", pady=(12, 0))

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
            "global": {
                "always_on_top": bool(self.v_top.get()),
                "open_window_on_mode": bool(self.v_open.get()),
                "opacity": float(self.v_opacity.get()),
            },
        }
        mode_settings.save(patch)
        self._cfg = mode_settings.get_section("perf")
        pts = int(self._cfg.get("history_points", 60))
        for g in (self.g_cpu, self.g_ram, self.g_gpu, self.g_net):
            g.set_max_points(pts)
        self.apply_window_prefs()
        self.set_status("reglages enregistres")

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

        # details overview
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
        self.ov_detail.configure(text="  ·  ".join(parts))
        self.ov_alerts.configure(
            text=("Alertes : " + ", ".join(alerts)) if alerts else "Aucune alerte seuil."
        )
        self.ov_alerts.configure(
            text_color=theme.ACCENT_DANGER if alerts else theme.TEXT_MUTED,
        )

        # sensors page
        self.sensor_lbls["cpu"].configure(
            text=f"Charge {snap.cpu_percent:.0f}% — {snap.cpu_count} threads logiques"
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
            text=" · ".join(tparts) if tparts else "Temperatures indisponibles (Windows)"
        )
        self.sensor_lbls["net"].configure(
            text=f"Descendant {format_net(snap.net_down_kbps)}  ·  Montant {format_net(snap.net_up_kbps)}"
        )
        self.set_status(f"live · {cfg.get('refresh_hz', 1.5):.1f} Hz")


def ouvrir_perf(master, on_close: Callable | None = None) -> PerfWindow:
    global _PERF_WIN
    if _PERF_WIN is not None:
        try:
            if _PERF_WIN.winfo_exists():
                _PERF_WIN.lift_focus()
                return _PERF_WIN
        except Exception:
            _PERF_WIN = None
    _PERF_WIN = PerfWindow(master, on_close=on_close)
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


def perf_ouverte() -> bool:
    try:
        return _PERF_WIN is not None and bool(_PERF_WIN.winfo_exists())
    except Exception:
        return False
