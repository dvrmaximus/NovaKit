# NovaKit

HUD type Jarvis **à partager** — inscription simple, discussion avec ton IA, mises à jour auto.

---

## Installation (3 étapes)

### 1. Télécharge

Sur [github.com/dvrmaximus/NovaKit](https://github.com/dvrmaximus/NovaKit) → **Code** → **Download ZIP**  
Dézippe le dossier où tu veux (Bureau, Documents…).

### 2. Installe

Double-clique **`Installer NovaKit.bat`**

- Vérifie Python  
- Installe les dépendances  
- Propose de lancer l’app  

Prérequis : [Python 3](https://www.python.org/downloads/) avec **Add python.exe to PATH**.

### 3. Lance

Double-clique **`Lancer NovaKit.bat`**

Au **premier lancement**, un assistant te demande ton pseudo, le nom de ton IA, et une [clé Google Gemini](https://aistudio.google.com/apikey) (gratuite).

---

Guide visuel (ouvrir dans le navigateur) : [`docs/index.html`](docs/index.html)

> Ne télécharge **pas** un `.exe` au hasard : le ZIP + ces deux `.bat` est le chemin prévu.

---

## Si Windows dit « virus »

Faux positif fréquent sur les kits open-source (`.bat`, scripts).

1. Utilise le ZIP de **ce** dépôt uniquement.  
2. SmartScreen → **Plus d’infos** → **Exécuter quand même**.  
3. Optionnel : exclusion Defender sur le dossier que **toi** as dézippé.

---

## Fichiers utiles (pour toi)

| Fichier | Rôle |
|---------|------|
| `Installer NovaKit.bat` | Installation guidée |
| `Lancer NovaKit.bat` | Lance l’app |
| `docs/index.html` | Page d’aide install |
| `version.json` | Version / MAJ auto |

Ne partage **jamais** ton `.env` ni le dossier `data/`.

---

## English (short)

1. Download ZIP from GitHub  
2. Run `Installer NovaKit.bat`  
3. Run `Lancer NovaKit.bat` — first launch opens the setup wizard (Gemini API key needed)
