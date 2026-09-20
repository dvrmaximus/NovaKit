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

    # —— Connexions Gmail / Google ——
    if any(
        x in t
        for x in (
            "connecte gmail", "connecter gmail", "connecte-moi a gmail",
            "connecte moi a gmail", "lie mon gmail", "lier gmail",
            "connecte google", "connecter google", "connecte-moi a google",
            "connecte moi a google", "lie mon google", "connexion gmail",
            "connexion google",
        )
    ) or (
        ("connecte" in t or "connecter" in t or "lie " in t or "lier " in t)
        and ("gmail" in t or "google" in t)
    ):
        from tools.gmail_tools import connecter_gmail
        return connecter_gmail()

    # —— Discord ——
    if any(
        x in t
        for x in (
            "connecte discord", "connecter discord", "connecte-moi a discord",
            "connecte moi a discord", "ouvre discord", "ouvrir discord",
            "lance discord", "lancer discord", "connexion discord",
        )
    ) or (("connecte" in t or "connecter" in t) and "discord" in t):
        from tools.discord_tools import connecter_discord
        return connecter_discord()

    m = re.search(
        r"(?:ouvre|ouvrir|lance|lancer)\s+(?:le\s+)?lien\s+discord\s+(.+)$",
        message.strip(),
        re.I,
    )
    if m or (("discord" in t) and ("http" in t or "discord.gg" in t or "discord.com" in t)):
        from tools.discord_tools import ouvrir_lien_discord
        url_m = re.search(r"(https?://\S+|discord\.gg/\S+|discord\.com/\S+)", message, re.I)
        if url_m:
            return ouvrir_lien_discord(url_m.group(1).rstrip(".,)"))
        if m:
            return ouvrir_lien_discord(m.group(1).strip())

    if any(
        x in t
        for x in (
            "envoie sur discord", "envoyer sur discord", "message discord",
            "dis sur discord", "poste sur discord", "envoi discord",
        )
    ):
        from tools.discord_tools import envoyer_webhook_discord
        contenu = re.sub(
            r"(?i).*?(?:envoie|envoyer|poste|dis)\s+(?:sur\s+)?discord\s*:?\s*",
            "",
            message,
            count=1,
        ).strip()
        if not contenu or contenu.lower() == message.lower().strip():
            contenu = re.sub(r"(?i).*?discord\s*:?\s*", "", message, count=1).strip()
        return envoyer_webhook_discord(contenu)

    # —— YouTube ——
    if "youtube" in t or "you tube" in t:
        from tools.web_tools import ouvrir_youtube
        m = re.search(
            r"(?:youtube|you\s*tube)\s+(?:sur\s+)?(.+)$",
            message.strip(),
            re.I,
        )
        if m:
            q = m.group(1).strip(" .!?")
            # ignore si juste « ouvre youtube »
            if q and _norm(q) not in ("ouvre", "ouvrir", "lance", "lancer", "s il te plait", "stp"):
                # « ouvre youtube musique relax » → extrait après youtube
                return ouvrir_youtube(q)
        m2 = re.search(
            r"(?:ouvre|ouvrir|lance|lancer|cherche|rechercher)\s+(?:sur\s+)?youtube\s+(.+)$",
            message.strip(),
            re.I,
        )
        if m2:
            return ouvrir_youtube(m2.group(1).strip(" .!?"))
        if any(x in t for x in ("ouvre", "ouvrir", "lance", "lancer", "cherche")):
            return ouvrir_youtube()

    # —— Apps (n'importe laquelle) ——
    m = re.search(
        r"^(?:ouvre|ouvrir|lance|lancer|demarre|demarrer|start)\s+(?:l['\u2019]appli(?:cation)?\s+|l['\u2019]app\s+|le\s+|la\s+|les\s+|le\s+jeu\s+|jeu\s+)?(.+)$",
        message.strip(),
        re.I,
    )
    if m:
        cible = m.group(1).strip(" .!?")
        from tools.web_tools import ouvrir_site_web
        sites = (
            "youtube", "gmail", "google", "netflix", "github",
            "twitter", "facebook", "reddit", "spotify",
        )
        tn = _norm(cible)
        for s in sites:
            if s in tn and "http" not in tn:
                if s == "youtube" and tn != "youtube":
                    from tools.web_tools import ouvrir_youtube
                    reste = re.sub(r"(?i)youtube", "", cible).strip()
                    return ouvrir_youtube(reste) if reste else ouvrir_youtube()
                return ouvrir_site_web(s)
        from tools.system_tools import ouvrir_application
        return ouvrir_application(cible)

    if t.startswith("ouvre") or t.startswith("lance") or "ouvre " in t or "lance " in t:
        from tools.system_tools import ouvrir_application
        from tools.web_tools import ouvrir_site_web
        apps = {
            "chrome": "chrome", "navigateur": "chrome", "edge": "edge",
            "spotify": "spotify", "musique": "spotify",
            "discord": "discord",
            "calculatrice": "calculatrice", "calculette": "calculatrice",
            "bloc-notes": "bloc-notes", "notepad": "notepad",
            "explorateur": "explorateur", "paint": "paint",
            "cursor": "cursor", "vscode": "vscode", "code": "vscode",
            "word": "word", "excel": "excel",
            "steam": "steam", "epic": "epic",
        }
        for cle, nom in apps.items():
            if cle in t:
                return ouvrir_application(nom)
        sites = ("youtube", "gmail", "google", "netflix", "github", "twitter", "spotify")
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
    if ("mail" in t or "gmail" in t) and any(
        x in t for x in ("lis", "lire", "dernier", "boite", "inbox", "nouveaux", "recus")
    ):
        from tools.gmail_tools import lire_derniers_mails
        return lire_derniers_mails(5)
    if t in ("mails", "mes mails", "gmail", "mes emails", "emails") or (
        ("mail" in t or "gmail" in t) and not any(x in t for x in ("connecte", "connecter", "ouvre", "ouvrir"))
    ):
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

    # —— Admin créateur (message / parler / ping / status uniquement) ——
    admin = _commande_admin_createur(t, message)
    if admin is not None:
        return admin

    return None


def _trouver_install(cible: str):
    """Résout un utilisateur par id, pseudo ou nom d'IA."""
    from online.admin_local import demarrer_admin_local
    from online.db import init_db, list_installs

    demarrer_admin_local(ouvrir=False, reset_mdp=False)
    init_db()
    users = list_installs(100)
    q = _norm(cible).strip()
    if not q:
        return None
    if q.isdigit():
        uid = int(q)
        for u in users:
            if u.get("id") == uid:
                return u
    for u in users:
        pseudo = _norm(u.get("pseudo") or "")
        nom_ia = _norm(u.get("nom_ia") or "")
        if q == pseudo or q == nom_ia or q in pseudo or q in nom_ia:
            return u
    return None


def _enqueue_safe(user: dict, action: str, texte: str = "") -> str:
    cid = (user.get("client_id") or "").strip()
    if not cid:
        return f"#{user.get('id')} hors ligne (pas de client_id)."
    from online.db import enqueue_command

    enqueue_command(cid, action, {"text": texte}, install_id=user.get("id"))
    label = user.get("pseudo") or user.get("nom_ia") or f"#{user.get('id')}"
    return f"OK — {action} → {label} (#{user.get('id')})."


def _commande_admin_createur(t: str, message: str) -> str | None:
    """Pilotage distant sûr : liste / message / parler / ping / status."""
    try:
        from online.admin_local import est_createur
        if not est_createur():
            return None
    except Exception:
        return None

    if any(
        x in t
        for x in (
            "liste utilisateur",
            "liste des utilisateur",
            "liste users",
            "mes utilisateur",
            "montre les utilisateur",
        )
    ) or t in ("utilisateurs", "liste utilisateurs"):
        try:
            from online.admin_local import demarrer_admin_local
            from online.db import init_db, list_installs

            demarrer_admin_local(ouvrir=False, reset_mdp=False)
            init_db()
            users = list_installs(40)
        except Exception as exc:
            return f"Admin indisponible : {exc}"
        if not users:
            return "Aucun utilisateur inscrit."
        lignes = []
        for u in users[:20]:
            lignes.append(
                f"#{u.get('id')} {u.get('pseudo') or '?'} · {u.get('nom_ia') or '?'} · "
                f"{'en ligne' if u.get('client_id') else 'hors ligne'}"
            )
        suite = f"\n… et {len(users) - 20} de plus." if len(users) > 20 else ""
        return f"{len(users)} utilisateur(s) :\n" + "\n".join(lignes) + suite

    m = re.search(
        r"(?:envoie(?:r)?\s+)?(?:un\s+)?message\s+(?:a|à)\s+([^\s:]+)(?:\s*[:\-]\s*|\s+)(.+)$",
        message.strip(),
        re.I,
    )
    if m:
        user = _trouver_install(m.group(1))
        if not user:
            return f"Utilisateur introuvable : {m.group(1)}"
        return _enqueue_safe(user, "message", m.group(2).strip())

    m = re.search(
        r"(?:fais\s+parler|faire\s+parler|parle(?:r)?\s+(?:a|à))\s+([^\s:]+)(?:\s*[:\-]\s*|\s+)(.+)$",
        message.strip(),
        re.I,
    )
    if m:
        user = _trouver_install(m.group(1))
        if not user:
            return f"Utilisateur introuvable : {m.group(1)}"
        return _enqueue_safe(user, "speak", m.group(2).strip())

    m = re.search(r"\bping\s+([^\s]+)\b", t)
    if m:
        user = _trouver_install(m.group(1))
        if not user:
            return f"Utilisateur introuvable : {m.group(1)}"
        return _enqueue_safe(user, "ping")

    m = re.search(r"\b(?:status|statut)\s+([^\s]+)\b", t)
    if m:
        user = _trouver_install(m.group(1))
        if not user:
            return f"Utilisateur introuvable : {m.group(1)}"
        return _enqueue_safe(user, "status", "Demande de statut")

    return None
