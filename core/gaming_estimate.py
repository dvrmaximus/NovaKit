"""Detection hardware + estimation presets jeux (heuristique)."""

from __future__ import annotations

import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_OK = False

_hw_cache: dict | None = None
_hw_lock = threading.Lock()
_bench_cancel = threading.Event()
_bench_running = False


@dataclass
class HardwareProfile:
    cpu_name: str = "CPU inconnu"
    cpu_cores: int = 0
    ram_gb: float = 0.0
    gpu_name: str = "GPU inconnu"
    gpu_vram_gb: float | None = None
    gpu_tier: int = 2  # 1 entry … 5 flagship
    notes: list[str] = field(default_factory=list)


@dataclass
class GameEstimate:
    scenario: str
    resolution: str
    fps_cible: int
    qualite: str
    shaders: str
    resume: str


# Tiers GPU approximatifs (score relatif)
_GPU_TIERS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"rtx\s*50[89]0|4090|4080\s*super|radeon\s*rx\s*79[05]0", re.I), 5),
    (re.compile(r"rtx\s*4070|4080|3080|3090|ti|radeon\s*rx\s*78[05]0|7900", re.I), 4),
    (re.compile(r"rtx\s*4060|3070|3060\s*ti|arc\s*a770|radeon\s*rx\s*67[05]0|6800|7600", re.I), 3),
    (re.compile(r"rtx\s*3050|3060|2060|1660|gtx\s*1660|arc\s*a750|radeon\s*rx\s*66[05]0|5700", re.I), 2),
    (re.compile(r"gtx\s*16|gtx\s*10|mx\s*\d|uhd|iris|radeon\s*graphics|vega|intel", re.I), 1),
]


def detect_hardware(force: bool = False) -> HardwareProfile:
    global _hw_cache
    with _hw_lock:
        if _hw_cache is not None and not force:
            return _hw_cache
        hw = _detect()
        _hw_cache = hw
        return hw


def _detect() -> HardwareProfile:
    hw = HardwareProfile()
    if PSUTIL_OK:
        try:
            hw.cpu_cores = int(psutil.cpu_count(logical=True) or 0)
            hw.ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            pass
    hw.cpu_name = _cpu_name() or platform.processor() or "CPU inconnu"
    hw.gpu_name, hw.gpu_vram_gb = _gpu_info()
    hw.gpu_tier = tier_gpu(hw.gpu_name)
    if hw.ram_gb and hw.ram_gb < 8:
        hw.notes.append("RAM limitee (< 8 Go) — vise 1080p medium.")
    if hw.gpu_tier <= 1:
        hw.notes.append("GPU entry / iGPU — presets competitifs low prioritaires.")
    return hw


def _cpu_name() -> str | None:
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3.0,
            creationflags=flags,
        )
        name = re.sub(r"\s+", " ", (out or "").strip())
        return name or None
    except Exception:
        return None


def _gpu_info() -> tuple[str, float | None]:
    # nvidia-smi d abord (VRAM fiable)
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
            creationflags=flags,
        )
        line = (out or "").strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if parts:
            vram = float(parts[1]) / 1024.0 if len(parts) > 1 else None
            return parts[0], vram
    except Exception:
        pass
    try:
        import GPUtil  # type: ignore
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            vram = float(g.memoryTotal) / 1024.0 if g.memoryTotal else None
            return g.name, vram
    except Exception:
        pass
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        out = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "$g = Get-CimInstance Win32_VideoController | Select-Object -First 1; Write-Output ($g.Name + '|' + $g.AdapterRAM)",
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3.0,
            creationflags=flags,
        )
        line = (out or "").strip()
        if line:
            name, _, ram_s = line.partition("|")
            vram = None
            try:
                ram_i = int(ram_s.strip() or "0")
                if ram_i > 0:
                    vram = round(ram_i / (1024 ** 3), 1)
            except Exception:
                vram = None
            if name.strip():
                return name.strip(), vram
    except Exception:
        pass
    return "GPU inconnu", None


def tier_gpu(name: str) -> int:
    for pat, tier in _GPU_TIERS:
        if pat.search(name or ""):
            return tier
    return 2


def estimer_presets(
    hw: HardwareProfile | None = None,
    aggressiveness: float = 0.5,
) -> list[GameEstimate]:
    """Heuristique honnete — pas une mesure reelle in-game.

    aggressiveness 0..1 : prudent ← → optimiste (decale le tier GPU).
    """
    hw = hw or detect_hardware()
    t = hw.gpu_tier
    ram = hw.ram_gb or 8.0
    # ajustement RAM
    if ram < 8:
        t = max(1, t - 1)
    elif ram >= 32 and t >= 3:
        t = min(5, t + 0)
    try:
        aggr = max(0.0, min(1.0, float(aggressiveness)))
    except (TypeError, ValueError):
        aggr = 0.5
    if aggr >= 0.75:
        t = min(5, t + 1)
    elif aggr <= 0.25:
        t = max(1, t - 1)

    def card(scenario, res, fps, qual, shaders, resume):
        return GameEstimate(scenario, res, fps, qual, shaders, resume)

    # Tables par scenario
    tables = {
        "Jeux competitifs (Valorant-like)": {
            1: ("1080p", 90, "low", "low", "vise 1080p low ~90 FPS"),
            2: ("1080p", 144, "medium", "low", "vise 1080p medium ~144"),
            3: ("1440p", 144, "high", "medium", "vise 1440p high ~144"),
            4: ("1440p", 240, "high", "high", "vise 1440p high ~240"),
            5: ("4K", 144, "ultra", "high", "vise 4K high/ultra ~144"),
        },
        "Battle royale (Fortnite-like)": {
            1: ("1080p", 60, "low", "low", "1080p low/performance ~60"),
            2: ("1080p", 90, "medium", "low", "1080p medium ~90"),
            3: ("1080p", 144, "high", "medium", "1080p high ~144"),
            4: ("1440p", 120, "high", "high", "1440p high ~120"),
            5: ("4K", 60, "epic", "high", "4K epic ~60 (shaders high)"),
        },
        "Open world (GTA-like)": {
            1: ("1080p", 40, "low", "low", "1080p low ~40-50"),
            2: ("1080p", 60, "medium", "medium", "1080p medium ~60"),
            3: ("1440p", 60, "high", "medium", "1440p high ~60"),
            4: ("1440p", 80, "very high", "high", "1440p very high ~80"),
            5: ("4K", 60, "ultra", "high", "4K ultra ~60"),
        },
        "AAA raytracing (Cyberpunk-like)": {
            1: ("1080p", 30, "low", "low", "1080p low, RT off"),
            2: ("1080p", 45, "medium", "low", "1080p medium, RT off"),
            3: ("1080p", 60, "high", "medium", "1080p high, RT off/DLSS"),
            4: ("1440p", 60, "high", "high", "1440p high + upscaling ~60"),
            5: ("4K", 60, "ultra", "high", "4K 60 avec shaders low/medium + DLSS"),
        },
    }

    out: list[GameEstimate] = []
    for scenario, by_tier in tables.items():
        row = by_tier.get(t) or by_tier[2]
        res, fps, qual, shaders, resume = row
        # cas special demande utilisateur style 4K 60 shaders low
        if scenario.startswith("AAA") and t >= 5:
            resume = "tu peux viser 4K 60 avec shaders low/medium + upscaling"
        if scenario.startswith("Jeux competitifs") and t >= 3 and ram >= 16:
            if t == 3:
                resume = "1080p ultra ~144 possible en competitif"
        out.append(card(scenario, res, fps, qual, shaders, resume))
    return out


def resume_vocal(hw: HardwareProfile | None = None) -> str:
    hw = hw or detect_hardware()
    est = estimer_presets(hw)
    lignes = [
        f"Config detectee : {hw.cpu_name}, {hw.ram_gb:.0f} Go RAM, {hw.gpu_name}.",
        "Estimations (indicatives, pas une mesure jeu) :",
    ]
    for e in est:
        lignes.append(
            f"- {e.scenario} : {e.resolution} {e.qualite}, shaders {e.shaders}, ~{e.fps_cible} FPS ({e.resume})"
        )
    lignes.append("Ce sont des approximations heuristiques.")
    return "\n".join(lignes)


def micro_benchmark(
    duree_s: float = 2.5,
    on_progress: Callable[[float], None] | None = None,
) -> dict:
    """Charge CPU legere + boucle synthetique — max quelques secondes, annulable."""
    global _bench_running
    _bench_cancel.clear()
    _bench_running = True
    t0 = time.perf_counter()
    ops = 0
    x = 1.000001
    try:
        while (time.perf_counter() - t0) < duree_s:
            if _bench_cancel.is_set():
                break
            # charge courte (pas de boucle chauffante longue)
            for _ in range(8000):
                x = x * 1.0000001 + 0.0000001
                ops += 1
            if on_progress:
                try:
                    on_progress(min(1.0, (time.perf_counter() - t0) / duree_s))
                except Exception:
                    pass
            time.sleep(0.002)  # laisse respirer le systeme
    finally:
        _bench_running = False
    elapsed = max(0.001, time.perf_counter() - t0)
    score = ops / elapsed / 1e6
    return {
        "ops_m_per_s": round(score, 2),
        "elapsed_s": round(elapsed, 2),
        "cancelled": _bench_cancel.is_set(),
        "dummy": x,
    }


def annuler_benchmark() -> None:
    _bench_cancel.set()


def benchmark_en_cours() -> bool:
    return _bench_running
