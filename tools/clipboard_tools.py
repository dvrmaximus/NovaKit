from win_silent import run_silent


def lire_presse_papier() -> str:
    """Lit le contenu actuel du presse-papier Windows."""
    try:
        result = run_silent(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
            text=True, timeout=5,
        )
        contenu = (result.stdout or "").strip()
        if not contenu:
            return "Le presse-papier est vide."
        return contenu[:500] + ("…" if len(contenu) > 500 else "")
    except Exception as e:
        return f"Impossible de lire le presse-papier : {e}"


def ecrire_presse_papier(texte: str) -> str:
    """Copie du texte dans le presse-papier Windows.

    Args:
        texte: contenu à copier
    """
    try:
        run_silent(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Set-Clipboard -Value $input"],
            input=texte, text=True, check=True, timeout=5,
        )
        return "Texte copié dans le presse-papier."
    except Exception as e:
        return f"Impossible d'écrire dans le presse-papier : {e}"
