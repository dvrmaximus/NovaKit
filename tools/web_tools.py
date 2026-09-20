import webbrowser
from urllib.parse import quote_plus

SITES_CONNUS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "musique": "https://open.spotify.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "twitter": "https://x.com",
    "github": "https://github.com",
    "facebook": "https://www.facebook.com",
    "reddit": "https://www.reddit.com",
    "discord": "https://discord.com/app",
}


def ouvrir_site_web(nom_ou_url: str) -> str:
    """Ouvre un site web dans le navigateur (YouTube, Google, Spotify, etc.).

    Args:
        nom_ou_url: nom du site ou URL complète
    """
    cle = nom_ou_url.lower().strip()
    url = SITES_CONNUS.get(cle)
    if url is None:
        url = nom_ou_url if nom_ou_url.startswith("http") else f"https://{nom_ou_url}"
    webbrowser.open(url)
    libelle = nom_ou_url if nom_ou_url.startswith("http") else nom_ou_url.strip().title()
    return f"J'ouvre {libelle}."


def ouvrir_youtube(requete: str = "") -> str:
    """Ouvre YouTube, éventuellement avec une recherche.

    Args:
        requete: texte à chercher (vide = page d'accueil)
    """
    q = (requete or "").strip()
    if q:
        webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(q)}")
        return f"YouTube — recherche « {q} »."
    webbrowser.open("https://www.youtube.com")
    return "J'ouvre YouTube."


def rechercher_sur_internet(requete: str) -> str:
    """Effectue une recherche web et renvoie un résumé des premiers résultats.

    Args:
        requete: ce que tu veux chercher sur internet
    """
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return "Recherche web indisponible (installe duckduckgo-search)."

    try:
        with DDGS() as ddgs:
            resultats = list(ddgs.text(requete, max_results=3))
        if not resultats:
            return "Aucun résultat trouvé."
        lignes = []
        for i, r in enumerate(resultats, 1):
            titre = r.get("title", "Sans titre")
            extrait = r.get("body", "")[:120]
            lignes.append(f"{i}. {titre} — {extrait}")
        return "\n".join(lignes)
    except Exception as erreur:
        return f"Recherche impossible : {erreur}"
