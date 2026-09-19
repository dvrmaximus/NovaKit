import urllib.parse
import urllib.request

from config import VILLE_DEFAUT


def obtenir_meteo(ville: str = "") -> str:
    """Renvoie la météo actuelle pour une ville.

    Args:
        ville: nom de la ville (Paris par défaut si non précisé)
    """
    ville = (ville or VILLE_DEFAUT).strip()
    url = f"https://wttr.in/{urllib.parse.quote(ville)}?format=j1&lang=fr"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Astat/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            import json
            data = json.loads(resp.read().decode())
        current = data["current_condition"][0]
        desc = current["lang_fr"][0]["value"] if current.get("lang_fr") else current["weatherDesc"][0]["value"]
        temp = current["temp_C"]
        ressenti = current["FeelsLikeC"]
        humidite = current["humidity"]
        return f"À {ville} : {desc}, {temp}°C (ressenti {ressenti}°C), humidité {humidite} %."
    except Exception as erreur:
        return f"Impossible d'obtenir la météo pour {ville} : {erreur}"
