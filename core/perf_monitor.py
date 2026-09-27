"""Telemetrie PC pour le mode Performance — psutil + GPU optionnel."""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_OK = False

_lock = threading.Lock()
_cache: dict[str, Any] = {"ts": 0.0, "snap": None}
_CACHE_TTL = 0.45
_net_prev: tuple[float, float, float] | None = None


@dataclass
class PerfSnapshot:
    cpu_percent: float = 0.0
    cpu_count: int = 0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_percent: float | None = None
    disk_used_gb: float | None = None
    disk_total_gb: float | None = None
    net_up_kbps: float | None = None
    net_down_kbps: float | None = None
    gpu_name: str | None = None
    gpu_percent: float | None = None
    gpu_vram_percent: float | None = None
    gpu_vram_used_gb: float | None = None
    gpu_vram_total_gb: float | None = None
    gpu_temp_c: float | None = None
    gpu_power_w: float | None = None
    cpu_name: str | None = None
    cpu_temp_c: float | None = None
    extras: dict[str, Any] = field(default_factory=dict)


def snapshot(force: bool = False) -> PerfSnapshot:
    now = time.monotonic()
    with _lock:
        if not force and _cache["snap"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
            return _cache["snap"]
        snap = _collect()
        _cache["ts"] = now
        _cache["snap"] = snap
        return snap


def _collect() -> PerfSnapshot:
    s = PerfSnapshot()
    if not PSUTIL_OK:
        return s
    try:
        s.cpu_percent = float(psutil.cpu_percent(interval=None))
        s.cpu_count = int(psutil.cpu_count() or 0)
    except Exception:
        pass
    try:
        vm = psutil.virtual_memory()
        s.ram_percent = float(vm.percent)
        s.ram_used_gb = vm.used / (1024 ** 3)
        s.ram_total_gb = vm.total / (1024 ** 3)
    except Exception:
        pass
    try:
        du = shutil.disk_usage("C:\\")
        s.disk_total_gb = du.total / (1024 ** 3)
        s.disk_used_gb = du.used / (1024 ** 3)
        s.disk_percent = (du.used / du.total) * 100.0 if du.total else None
    except Exception:
        try:
            usage = psutil.disk_usage("/")
            s.disk_total_gb = usage.total / (1024 ** 3)
            s.disk_used_gb = usage.used / (1024 ** 3)
            s.disk_percent = float(usage.percent)
        except Exception:
            pass
    global _net_prev
    try:
        io = psutil.net_io_counters()
        now = time.monotonic()
        if _net_prev is not None:
            dt = max(0.05, now - _net_prev[0])
            s.net_up_kbps = (io.bytes_sent - _net_prev[1]) / dt / 1024.0
            s.net_down_kbps = (io.bytes_recv - _net_prev[2]) / dt / 1024.0
        _net_prev = (now, float(io.bytes_sent), float(io.bytes_recv))
    except Exception:
        pass
    _fill_gpu(s)
    _fill_temps(s)
    _fill_cpu_name(s)
    return s


def _fill_cpu_name(s: PerfSnapshot) -> None:
    try:
        from core.gaming_estimate import detect_hardware
        hw = detect_hardware()
        if hw and hw.cpu_name:
            s.cpu_name = hw.cpu_name
    except Exception:
        pass


def _fill_temps(s: PerfSnapshot) -> None:
    if not PSUTIL_OK:
        return
    try:
        temps = psutil.sensors_temperatures(fahrenheit=False)
    except Exception:
        temps = None
    if not temps:
        return
    for key in ("coretemp", "k10temp", "acpitz", "cpu_thermal", "nvme"):
        entries = temps.get(key) or []
        if entries and entries[0].current is not None:
            s.cpu_temp_c = float(entries[0].current)
            break
    if s.cpu_temp_c is None:
        for entries in temps.values():
            if entries and entries[0].current is not None:
                s.cpu_temp_c = float(entries[0].current)
                break


def _fill_gpu(s: PerfSnapshot) -> None:
    if _gpu_gputil(s):
        return
    if _gpu_nvidia_smi(s):
        return
    name = _gpu_name_wmi()
    if name:
        s.gpu_name = name


def _gpu_gputil(s: PerfSnapshot) -> bool:
    try:
        import GPUtil  # type: ignore
        gpus = GPUtil.getGPUs()
        if not gpus:
            return False
        g = gpus[0]
        s.gpu_name = g.name
        s.gpu_percent = float(g.load * 100.0)
        if g.memoryTotal:
            s.gpu_vram_total_gb = float(g.memoryTotal) / 1024.0
            s.gpu_vram_used_gb = float(g.memoryUsed) / 1024.0
            s.gpu_vram_percent = (g.memoryUsed / g.memoryTotal) * 100.0
        if g.temperature is not None:
            s.gpu_temp_c = float(g.temperature)
        return True
    except Exception:
        return False


def _gpu_nvidia_smi(s: PerfSnapshot) -> bool:
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
            creationflags=flags,
        )
        line = (out or "").strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            return False
        s.gpu_name = parts[0]
        s.gpu_percent = float(parts[1])
        used = float(parts[2])
        total = float(parts[3])
        s.gpu_vram_used_gb = used / 1024.0
        s.gpu_vram_total_gb = total / 1024.0
        s.gpu_vram_percent = (used / total) * 100.0 if total else None
        s.gpu_temp_c = float(parts[4])
        if len(parts) >= 6:
            try:
                pw = parts[5].replace("[N/A]", "").strip()
                if pw:
                    s.gpu_power_w = float(pw)
            except (TypeError, ValueError):
                pass
        return True
    except Exception:
        return False


def _gpu_name_wmi() -> str | None:
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name)",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3.0,
            creationflags=flags,
        )
        name = (out or "").strip()
        return name or None
    except Exception:
        return None


def format_net(kbps: float | None) -> str:
    if kbps is None:
        return "—"
    if kbps < 1024:
        return f"{kbps:.0f} Ko/s"
    return f"{kbps / 1024.0:.1f} Mo/s"
