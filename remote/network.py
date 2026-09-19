import socket

from config import REMOTE_PORT
from win_silent import run_silent


def obtenir_ip_wifi() -> str:
    """IP locale sur le réseau WiFi/LAN (interface par défaut)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def ouvrir_parefeu(port: int = REMOTE_PORT) -> bool:
    """Autorise le port Astat dans le pare-feu Windows."""
    try:
        run_silent(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name=Astat Remote ({port})",
                "dir=in", "action=allow", "protocol=TCP",
                f"localport={port}",
            ],
            timeout=10, check=False,
        )
        return True
    except Exception:
        return False


def parefeu_autorise() -> bool:
    try:
        r = run_silent(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            text=True, timeout=10,
        )
        return f"Astat Remote ({REMOTE_PORT})" in (r.stdout or "")
    except Exception:
        return False
