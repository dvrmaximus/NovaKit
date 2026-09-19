# NovaKit

HUD type Jarvis **à partager** : inscription simple + discussion avec ton IA + **MAJ auto**.

## Pour tes potes (qui reçoivent le zip)

1. `install.bat`
2. `Lancer NovaKit.vbs`
3. 3 écrans : **prénom** + **nom de l’IA** → **clé Gemini** → **PIN**
4. Bouton **DISCUSSION AVEC L'IA**

## Pour toi (créateur) — 2 minutes

Double-clique **`Configurer Notifs.bat`** :

### 1) Inscriptions (mail)
1. Va sur https://formspree.io (gratuit)
2. New Form → copie l’URL `https://formspree.io/f/xxxxx`
3. Colle-la dans le champ **Inscriptions**

→ À chaque install tu reçois un **mail** (pseudo + nom d’IA). Pas de clé API.

### 2) Mises à jour auto
1. Mets NovaKit sur **GitHub** (ou un hébergeur de fichiers)
2. En ligne, garde un fichier `version.json` :

```json
{
  "version": "1.1.0",
  "zip_url": "https://github.com/TOI/NovaKit/archive/refs/heads/main.zip",
  "notes": "Améliorations HUD"
}
```

3. Colle l’URL raw de ce fichier dans **Mises à jour**  
   ex. `https://raw.githubusercontent.com/TOI/NovaKit/main/version.json`

Quand tu publies une nouvelle version (augmente `version` + `zip_url`), au prochain lancement tes potes voient « Installer la mise à jour ? » — leurs `.env` et données sont **gardés**.

## Fichiers utiles

| Fichier | Rôle |
|---------|------|
| `Configurer Notifs.bat` | Tes 2 liens (mail + MAJ) |
| `version.json` | Version locale / modèle à publier |
| `creator.json` | Config sauvegardée |
| `Reset Setup.bat` | Refaire l’inscription |

## Important

- Ne partage **jamais** ton `.env`
- Tu peux (et dois) partager `creator.json` **avec** tes liens Formspree / update
