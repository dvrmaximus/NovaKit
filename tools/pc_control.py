import ctypes
import socket
from datetime import datetime
from pathlib import Path

from config import DATA_DIR
from win_silent import run_silent

SCREENSHOT_DIR = DATA_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def obtenir_ip_locale() -> str:
    """Renvoie l'adresse IP locale du PC sur le réseau WiFi/LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "IP inconnue"


def verrouiller_ecran() -> str:
    """Verrouille la session Windows (écran de connexion)."""
    try:
        ctypes.windll.user32.LockWorkStation()
        return "Écran verrouillé."
    except Exception as e:
        return f"Impossible de verrouiller : {e}"


def eteindre_ordinateur(dans_minutes: int = 1) -> str:
    """Éteint le PC après un délai en minutes.

    Args:
        dans_minutes: délai avant extinction (1 par défaut)
    """
    try:
        secondes = max(0, int(dans_minutes)) * 60
        run_silent(["shutdown", "/s", "/t", str(secondes)], check=True)
        return f"Extinction programmée dans {dans_minutes} minute(s)."
    except Exception as e:
        return f"Impossible de programmer l'extinction : {e}"


def redemarrer_ordinateur(dans_minutes: int = 1) -> str:
    """Redémarre le PC après un délai en minutes.

    Args:
        dans_minutes: délai avant redémarrage (1 par défaut)
    """
    try:
        secondes = max(0, int(dans_minutes)) * 60
        run_silent(["shutdown", "/r", "/t", str(secondes)], check=True)
        return f"Redémarrage programmé dans {dans_minutes} minute(s)."
    except Exception as e:
        return f"Impossible de programmer le redémarrage : {e}"


def annuler_extinction() -> str:
    """Annule une extinction ou un redémarrage programmé."""
    try:
        run_silent(["shutdown", "/a"], check=True)
        return "Extinction/redémarrage annulé."
    except Exception:
        return "Aucune extinction en attente."


def mettre_en_veille() -> str:
    """Met le PC en veille."""
    try:
        run_silent(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
        return "Mise en veille."
    except Exception as e:
        return f"Impossible de mettre en veille : {e}"


def capturer_ecran() -> str:
    """Prend une capture d'écran et la sauvegarde (consultable depuis le téléphone)."""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        chemin = SCREENSHOT_DIR / "latest.png"
        horodate = SCREENSHOT_DIR / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        img.save(chemin)
        img.save(horodate)
        return f"Capture enregistrée. Consulte-la depuis ton téléphone."
    except Exception as e:
        return f"Capture impossible : {e}"


def ecrire_texte(texte: str) -> str:
    """Tape du texte dans la fenêtre active (comme un clavier).

    Args:
        texte: le texte à taper
    """
    try:
        import pyautogui
        import pyperclip
        pyperclip.copy(texte)
        pyautogui.hotkey("ctrl", "v")
        return f"Texte tapé : « {texte[:40]}{'…' if len(texte) > 40 else ''} »"
    except Exception as e:
        return f"Impossible de taper le texte : {e}"


def raccourci_clavier(raccourci: str) -> str:
    """Envoie un raccourci clavier, par exemple ctrl+c, alt+tab, win+d.

    Args:
        raccourci: combinaison de touches séparées par +
    """
    try:
        import pyautogui
        touches = [t.strip().lower() for t in raccourci.split("+")]
        pyautogui.hotkey(*touches)
        return f"Raccourci {raccourci} envoyé."
    except Exception as e:
        return f"Raccourci impossible : {e}"


def commande_media(action: str) -> str:
    """Contrôle la lecture multimédia : play, pause, suivant, precedent, stop.

    Args:
        action: play, pause, suivant, precedent ou stop
    """
    try:
        import pyautogui
        mapping = {
            "play": "playpause", "pause": "playpause", "playpause": "playpause",
            "suivant": "nexttrack", "next": "nexttrack",
            "precedent": "prevtrack", "prev": "prevtrack",
            "stop": "stop",
        }
        touche = mapping.get(action.lower().strip())
        if not touche:
            return "Action inconnue. Utilise : play, pause, suivant, precedent, stop."
        pyautogui.press(touche)
        return f"Commande média : {action}."
    except Exception as e:
        return f"Commande média impossible : {e}"
