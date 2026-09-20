# Outils créateur (toi uniquement)

Ces scripts **ne sont pas** destinés aux potes qui téléchargent NovaKit.
Ils restent dans le dépôt pour toi, mais ne sont liés ni depuis le README public ni depuis l’installateur.

## Lanceurs

| Fichier | Rôle |
|---------|------|
| `Lancer Systeme Online.bat` | Panel admin + tunnel public (laisse la fenêtre ouverte) |
| `Lancer Admin Utilisateurs.bat` | Admin local http://127.0.0.1:8788 |
| `Configurer Notifs.bat` | Formspree / Discord / URL de MAJ (`creator.json`) |

## Compte admin

Après le premier lancement d’un de ces outils, un fichier local `data/admin_credentials.txt` est créé.
C’est **ce fichier** (gitignoré) qui active le mode créateur dans l’app — pas le `creator.json` partagé.

Identifiants par défaut : **Lutre** / **LutreAdmin** (à changer en prod si besoin).

## Mises à jour pour les potes

Sur GitHub, mets à jour `version.json` :

```json
{
  "version": "1.1.0",
  "zip_url": "https://github.com/dvrmaximus/NovaKit/archive/refs/heads/main.zip",
  "notes": "Améliorations HUD"
}
```

`creator.json` peut être partagé **avec** tes liens Formspree / update — jamais `.env` ni `data/`.

## Build exe (avancé)

Voir `scripts\Build Application.bat` puis `scripts\Installer Application.bat`.
