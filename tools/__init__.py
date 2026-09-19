from tools.clipboard_tools import ecrire_presse_papier, lire_presse_papier
from tools.datetime_tools import calculer, obtenir_date_actuelle, obtenir_heure_actuelle
from tools.gmail_tools import connecter_gmail, deconnecter_gmail, lire_derniers_mails
from tools.notes_tools import ajouter_note, lire_notes
try:
    from tools.pc_control import (
        annuler_extinction, capturer_ecran, commande_media, ecrire_texte,
        eteindre_ordinateur, mettre_en_veille, obtenir_ip_locale, raccourci_clavier,
        redemarrer_ordinateur, verrouiller_ecran,
    )
    _PC_TOOLS = [
        verrouiller_ecran, eteindre_ordinateur, redemarrer_ordinateur,
        annuler_extinction, mettre_en_veille, capturer_ecran, ecrire_texte,
        raccourci_clavier, commande_media, obtenir_ip_locale,
    ]
except ImportError:
    _PC_TOOLS = []
from tools.reminders_tools import creer_rappel, lister_rappels
from tools.system_tools import ouvrir_application
from tools.weather_tools import obtenir_meteo
from tools.web_tools import ouvrir_site_web

ALL_TOOLS = [
    obtenir_heure_actuelle,
    obtenir_date_actuelle,
    calculer,
    ouvrir_application,
    ouvrir_site_web,
    lire_derniers_mails,
    connecter_gmail,
    deconnecter_gmail,
    obtenir_meteo,
    ajouter_note,
    lire_notes,
    creer_rappel,
    lister_rappels,
    lire_presse_papier,
    ecrire_presse_papier,
] + _PC_TOOLS

try:
    from tools.web_tools import rechercher_sur_internet
    ALL_TOOLS.append(rechercher_sur_internet)
except ImportError:
    pass

try:
    from tools.system_tools import ajuster_volume, regler_volume, obtenir_volume
    ALL_TOOLS.extend([regler_volume, obtenir_volume, ajuster_volume])
except ImportError:
    pass
