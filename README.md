# NovaKit

HUD type Jarvis **à partager** : inscription simple + discussion avec ton IA + **MAJ auto**.

## Application Windows

1. `Build Application.bat` → crée `dist\NovaKit\NovaKit.exe`
2. `Installer Application.bat` → installe dans `%LOCALAPPDATA%\Programs\NovaKit`
3. Raccourci **NovaKit** sur le Bureau + Menu Démarrer

Ensuite tu lances NovaKit comme n’importe quelle app (plus besoin de Python visible).

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
| `NovaKit` (Bureau) | Lance l’application installée |
| `Installer Application.bat` | Installe l’app + raccourcis |
| `Build Application.bat` | Reconstruit le `.exe` |
| `Lancer Systeme Online.bat` | Panel admin + tunnel public |
| `Configurer Notifs.bat` | Liens mail / MAJ / online |
| `version.json` | Version locale / modèle à publier |
| `creator.json` | Config sauvegardée |
| `Reset Setup.bat` | Refaire l’inscription |

## Important

- Ne partage **jamais** ton `.env`
- Tu peux (et dois) partager `creator.json` **avec** tes liens Formspree / update
