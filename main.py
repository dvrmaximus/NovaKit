"""Point d'entrée NovaKit — setup, MAJ auto, HUD."""

import sys
import traceback
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

try:
    from win_silent import patch_subprocess_no_window
    patch_subprocess_no_window()
except Exception:
    pass

_data = ROOT / "data"
_data.mkdir(exist_ok=True)
if sys.stdout is None:
    sys.stdout = open(_data / "stdout.log", "a", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(_data / "stderr.log", "a", encoding="utf-8")


def _afficher(message: str, titre: str = "NovaKit"):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, titre, 0x40)
    except Exception:
        print(message)


def _afficher_erreur(message: str):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "NovaKit — Erreur", 0x10)
    except Exception:
        print(message, file=sys.stderr)


def _relancer():
    from win_silent import popen_silent
    if getattr(sys, "frozen", False):
        popen_silent([sys.executable])
        return
    main = str(Path(__file__).resolve())
    exe = Path(sys.executable)
    pw = exe.with_name("pythonw.exe")
    if pw.exists():
        popen_silent([str(pw), main])
    else:
        popen_silent(["pyw", "-3", main])


def _check_update_blocking() -> bool:
    """True si une MAJ a été appliquée (il faut relancer)."""
    try:
        from core.updater import appliquer_mise_a_jour, verifier_mise_a_jour
        info = verifier_mise_a_jour()
        if not info:
            return False
        notes = info.get("notes") or ""
        msg = (
            f"Mise à jour disponible : {info['local']} → {info['version']}\n\n"
            f"{notes}\n\n"
            "Ton compte, e-mail, PIN et Gmail sont CONSERVÉS.\n"
            "Une sauvegarde ZIP est faite avant l'install.\n\n"
            "Installer maintenant ?"
        )
        try:
            import ctypes
            # MB_YESNO = 4, IDYES = 6
            choix = ctypes.windll.user32.MessageBoxW(0, msg, "NovaKit — Mise à jour", 0x4 | 0x20)
            if choix != 6:
                return False
        except Exception:
            pass
        appliquer_mise_a_jour(info)
        _afficher(
            f"NovaKit {info['version']} installé.\n"
            "Compte conservé — pas besoin de te reconnecter.\nRedémarrage…",
            "NovaKit",
        )
        _relancer()
        return True
    except Exception as exc:
        print(f"[update] {exc}")
        return False


def _lancer_hud():
    import importlib
    import config
    importlib.reload(config)
    from ui.app import lancer
    lancer()


if __name__ == "__main__":
    try:
        from config import est_configure

        if not est_configure():
            from ui.setup_wizard import lancer_setup
            lancer_setup()
            import importlib
            import config
            importlib.reload(config)
            if not config.est_configure():
                sys.exit(0)
        else:
            # MAJ zip = sources ; l'app .exe se met à jour autrement
            if not getattr(sys, "frozen", False) and _check_update_blocking():
                sys.exit(0)

        _lancer_hud()
    except Exception as exc:
        log = ROOT / "novakit_error.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        _afficher_erreur(
            f"Impossible de lancer NovaKit.\n\n{exc}\n\nDétails dans :\n{log}"
        )
        sys.exit(1)
