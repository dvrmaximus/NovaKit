# NovaKit

HUD type Jarvis **à partager** : inscription simple + discussion avec ton IA + **MAJ auto**.

## Installation recommandée (source GitHub)

1. Sur [github.com/dvrmaximus/NovaKit](https://github.com/dvrmaximus/NovaKit) → **Code** → **Download ZIP**
2. Dézippe le dossier quelque part (ex. Bureau)
3. Double-clique **`install.bat`** (installe les dépendances Python)
4. Double-clique **`Lancer NovaKit.bat`**

Prérequis : [Python 3](https://www.python.org/downloads/) avec l’option **Add python.exe to PATH**.

Ne télécharge **pas** un `.exe` au hasard : le ZIP source + les `.bat` ci-dessus est le chemin prévu pour les potes.

## Application Windows (optionnel, créateur)

Si tu veux un `.exe` local (PyInstaller) :

1. `Build Application.bat` → crée `dist\NovaKit\NovaKit.exe` (non versionné, non signé)
2. `Installer Application.bat` → installe dans `%LOCALAPPDATA%\Programs\NovaKit`
3. Raccourci **NovaKit** sur le Bureau + Menu Démarrer

L’exe non signé peut être signalé par Windows / antivirus : préfère le ZIP source pour partager.

## Si Windows dit « virus »

C’est en général un **faux positif**. NovaKit est du Python open-source : pas de voleur de mots de passe, pas de payload téléchargé en secret. Les outils de type kit (`.bat`, scripts, éventuellement un `.exe` PyInstaller non signé) ressemblent parfois à des droppers pour SmartScreen / Defender.

**Quoi faire :**

1. Préfère **Download ZIP** de la branche `main`, puis `install.bat` + `Lancer NovaKit.bat` (pas un exe trouvé ailleurs).
2. Si SmartScreen s’affiche : **Plus d’infos** → **Exécuter quand même** / **Autoriser**.
3. Après installation / dézip, tu peux ajouter le dossier NovaKit en **exclusion** Windows Defender (Paramètres → Virus et menaces → Exclusions) si les alertes insistent — uniquement pour un dossier que **tu** as choisi et dont tu connais la provenance (ce dépôt).
4. Vérifie l’URL : `https://github.com/dvrmaximus/NovaKit` uniquement.

## Pour toi (créateur) — système online + admin

1. Double-clique **`Lancer Systeme Online.bat`**
2. Un compte admin **Lutre** est créé (mot de passe dans `data/admin_credentials.txt`)
3. Un tunnel public s’ouvre → panel web des installations
4. L’URL est écrite dans `creator.json` (`online_api_url`) pour que les potes s’inscrivent chez toi

Laisse la fenêtre ouverte pour rester en ligne.

Optionnel : **`Configurer Notifs.bat`** pour Formspree (mail) + lien `version.json` GitHub.

### Mises à jour auto
Sur GitHub, mets à jour `version.json` :

```json
{
  "version": "1.1.0",
  "zip_url": "https://github.com/dvrmaximus/NovaKit/archive/refs/heads/main.zip",
  "notes": "Améliorations HUD"
}
```

Quand tu publies une nouvelle version, au prochain lancement tes potes voient « Installer la mise à jour ? » — leurs `.env` et données sont **gardés**.

## Fichiers utiles

| Fichier | Rôle |
|---------|------|
| `install.bat` | Dépendances Python |
| `Lancer NovaKit.bat` | Lance l’app (source) |
| `Installer Application.bat` | Installe l’app + raccourcis (après build) |
| `Build Application.bat` | Reconstruit le `.exe` local |
| `Lancer Systeme Online.bat` | Panel admin + tunnel public |
| `Configurer Notifs.bat` | Liens mail / MAJ / online |
| `version.json` | Version locale / modèle à publier |
| `creator.json` | Config sauvegardée |
| `Reset Setup.bat` | Refaire l’inscription |

## Important

- Ne partage **jamais** ton `.env` ni le dossier `data/`
- Tu peux (et dois) partager `creator.json` **avec** tes liens Formspree / update
- Les fichiers `.vbs`, `.lnk` et `.exe` ne sont pas dans le dépôt (évite les faux positifs)
