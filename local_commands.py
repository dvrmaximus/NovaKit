"""Commandes locales sans Gemini — utile si le quota API est saturé."""

from __future__ import annotations

import re


def _norm(texte: str) -> str:
    t = (texte or "").lower().strip()
    for a, b in (("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a"), ("ù", "u"), ("ô", "o")):
        t = t.replace(a, b)
    return t


def executer_commande_locale(message: str) -> str | None:
    """
    Si la commande est reconnue localement, exécute l'outil et renvoie la réponse.
    Sinon renvoie None (il faudra Gemini).
    """
    t = _norm(message)
    if not t:
        return None

    # —— Heure / date ——
    if any(x in t for x in ("quelle heure", "l heure", "heure est")):
        from tools.datetime_tools import obtenir_heure_actuelle
        return f"Il est {obtenir_heure_actuelle()}."

    if any(x in t for x in ("quelle date", "on est quel jour", "jour sommes")):
        from tools.datetime_tools import obtenir_date_actuelle
        return f"Nous sommes le {obtenir_date_actuelle()}."

    # —— Météo ——
    if "meteo" in t or "temps fait" in t or "quel temps" in t:
        from tools.weather_tools import obtenir_meteo
        m = re.search(r"(?:a|à|pour)\s+([a-zA-Zàâäéèêëïîôùûüç\-\s]{2,40})$", message.strip(), re.I)
        ville = m.group(1).strip() if m else ""
        return obtenir_meteo(ville)

    # —— Volume ——
    m = re.search(r"volume\s*(?:a|à|de)?\s*(\d{1,3})", t)
    if m and ("volume" in t or "son" in t):
        from tools.system_tools import regler_volume
        return regler_volume(int(m.group(1)))
    if "monte" in t and "volume" in t:
        try:
            from tools.system_tools import ajuster_volume
            return ajuster_volume(15)
        except Exception:
            pass
    if ("baisse" in t or "diminue" in t) and "volume" in t:
        try:
            from tools.system_tools import ajuster_volume
            return ajuster_volume(-15)
        except Exception:
            pass

    # —— Apps (n'importe laquelle) ——
    m = re.search(
        r"^(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|start)\s+(?:l['\u2019]appli(?:cation)?\s+|l['\u2019]app\s+|le\s+|la\s+|les\s+)?(.+)$",
        message.strip(),
        re.I,
    )
    if m:
        cible = m.group(1).strip(" .!?")
        # Sites web connus
        from tools.web_tools import ouvrir_site_web
        sites = ("youtube", "gmail", "google", "netflix", "github", "twitter", "facebook", "reddit")
        tn = _norm(cible)
        for s in sites:
            if s in tn and "http" not in tn:
                return ouvrir_site_web(s)
        from tools.system_tools import ouvrir_application
        return ouvrir_application(cible)

    if t.startswith("ouvre") or t.startswith("lance") or "ouvre " in t or "lance " in t:
        from tools.system_tools import ouvrir_application
        from tools.web_tools import ouvrir_site_web
        apps = {
            "chrome": "chrome", "navigateur": "chrome",
            "spotify": "spotify", "musique": "spotify",
            "discord": "discord",
            "calculatrice": "calculatrice", "calculette": "calculatrice",
            "bloc-notes": "bloc-notes", "notepad": "notepad",
            "explorateur": "explorateur", "paint": "paint",
            "cursor": "cursor", "vscode": "vscode", "code": "vscode",
            "word": "word", "excel": "excel",
        }
        for cle, nom in apps.items():
            if cle in t:
                return ouvrir_application(nom)
        sites = ("youtube", "gmail", "google", "netflix", "github", "twitter")
        for s in sites:
            if s in t:
                return ouvrir_site_web(s)

    # —— PC ——
    if "verrouille" in t or "verrouiller" in t or "lock" in t:
        from tools.pc_control import verrouiller_ecran
        return verrouiller_ecran()
    if "veille" in t:
        from tools.pc_control import mettre_en_veille
        return mettre_en_veille()
    if "annule" in t and ("extinction" in t or "shutdown" in t or "eteindre" in t):
        from tools.pc_control import annuler_extinction
        return annuler_extinction()
    if "eteins" in t or "eteindre" in t or "shutdown" in t:
        from tools.pc_control import eteindre_ordinateur
        m = re.search(r"(\d+)\s*min", t)
        return eteindre_ordinateur(int(m.group(1)) if m else 1)
    if "redemarre" in t or "restart" in t:
        from tools.pc_control import redemarrer_ordinateur
        return redemarrer_ordinateur(1)
    if "capture" in t or "screenshot" in t:
        from tools.pc_control import capturer_ecran
        return capturer_ecran()

    # —— Média ——
    if any(x in t for x in ("pause", "play", "lecture", "musique")):
        from tools.pc_control import commande_media
        if "suivant" in t or "next" in t:
            return commande_media("suivant")
        if "precedent" in t or "prev" in t:
            return commande_media("precedent")
        return commande_media("pause")
    if "piste suivante" in t or "suivant" in t and ("piste" in t or "morceau" in t):
        from tools.pc_control import commande_media
        return commande_media("suivant")

    # —— Gmail / notes ——
    if "connecte gmail" in t or "connecter gmail" in t:
        from tools.gmail_tools import connecter_gmail
        return connecter_gmail()
    if "mail" in t or "gmail" in t:
        from tools.gmail_tools import lire_derniers_mails
        return lire_derniers_mails(5)
    if t.startswith("note ") or "ajoute une note" in t or "note :" in t:
        from tools.notes_tools import ajouter_note
        contenu = re.sub(r"(?i)^(ajoute\s+une\s+)?note\s*:?\s*", "", message).strip()
        return ajouter_note(contenu or message)

    # —— IP ——
    if "adresse ip" in t or "quelle ip" in t or "mon ip" in t:
        from tools.pc_control import obtenir_ip_locale
        return f"IP locale : {obtenir_ip_locale()}"

    return None
