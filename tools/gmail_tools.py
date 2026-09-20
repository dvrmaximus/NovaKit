from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import BASE_DIR, DATA_DIR

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = DATA_DIR / "gmail_token.json"
TOKEN_LEGACY = BASE_DIR / "token.json"

_service_gmail = None


def _trouver_credentials() -> Optional[Path]:
    cred = BASE_DIR / "credentials.json"
    if cred.exists():
        return cred
    fichiers = list(BASE_DIR.glob("client_secret*.json"))
    return fichiers[0] if fichiers else None


def _chemin_token() -> Path:
    if TOKEN_FILE.exists():
        return TOKEN_FILE
    if TOKEN_LEGACY.exists():
        return TOKEN_LEGACY
    return TOKEN_FILE


def _sauver_token(creds: Credentials):
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    # Nettoie l'ancien token à la racine pour éviter le chaos
    if TOKEN_LEGACY.exists() and TOKEN_LEGACY != TOKEN_FILE:
        try:
            TOKEN_LEGACY.unlink()
        except Exception:
            pass


def gmail_est_connecte() -> bool:
    """True si un token valide (ou rafraîchissable) existe — sans ouvrir de navigateur."""
    try:
        chemin = _chemin_token()
        if not chemin.exists():
            return False
        creds = Credentials.from_authorized_user_file(str(chemin), GMAIL_SCOPES)
        if creds and creds.valid:
            return True
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _sauver_token(creds)
            return True
    except Exception:
        return False
    return False


def _marquer_connexion_demandee():
    try:
        (DATA_DIR / "gmail_connect.flag").write_text("1", encoding="utf-8")
    except Exception:
        pass


def _ouvrir_gmail_navigateur() -> str:
    """Sans OAuth : ouvre Gmail / compte Google dans le navigateur."""
    import webbrowser
    _marquer_connexion_demandee()
    webbrowser.open("https://accounts.google.com/AccountChooser?continue=https://mail.google.com")
    return (
        "J'ouvre Gmail dans le navigateur — connecte-toi avec ton compte Google. "
        "Pour lire les mails depuis Nova, place un credentials.json Google OAuth "
        "à la racine du dossier, puis redis « connecte Gmail »."
    )


def connecter_gmail(forcer: bool = False) -> str:
    """Connecte Gmail une fois (OAuth). Sinon ouvre Gmail dans le navigateur."""
    global _service_gmail
    if not forcer and gmail_est_connecte():
        return "Gmail est déjà connecté. Tu restes connecté même après un redémarrage."

    chemin = _trouver_credentials()
    if not chemin:
        return _ouvrir_gmail_navigateur()

    try:
        _marquer_connexion_demandee()
        flow = InstalledAppFlow.from_client_secrets_file(str(chemin), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        _sauver_token(creds)
        _service_gmail = None  # force rebuild
        obtenir_service_gmail()
        return "Gmail connecté. Tu resteras connecté automatiquement."
    except Exception as erreur:
        msg = str(erreur)
        if "access_denied" in msg or "403" in msg:
            return (
                "Google bloque encore : ajoute ton adresse "
                "comme utilisateur test dans la console Google Cloud, "
                "puis redis « connecte Gmail »."
            )
        # Dernier recours : login web
        try:
            return _ouvrir_gmail_navigateur() + f" (OAuth : {erreur})"
        except Exception:
            return f"Connexion Gmail impossible : {erreur}"


def deconnecter_gmail() -> str:
    """Supprime le token (il faudra se reconnecter)."""
    global _service_gmail
    _service_gmail = None
    for chemin in (TOKEN_FILE, TOKEN_LEGACY):
        if chemin.exists():
            chemin.unlink()
    return "Gmail déconnecté. Dis « connecte Gmail » pour te reconnecter."


def obtenir_service_gmail():
    global _service_gmail
    if _service_gmail is not None:
        return _service_gmail

    chemin_token = _chemin_token()
    creds = None
    if chemin_token.exists():
        creds = Credentials.from_authorized_user_file(str(chemin_token), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                _sauver_token(creds)
            except Exception as exc:
                raise RuntimeError(
                    "Session Gmail expirée. Dis « connecte Gmail » pour te reconnecter."
                ) from exc
        else:
            raise RuntimeError(
                "Gmail n'est pas encore connecté. Dis « connecte Gmail » une seule fois."
            )

    _service_gmail = build("gmail", "v1", credentials=creds)
    return _service_gmail


def lire_derniers_mails(nombre: int = 5) -> str:
    """Lit les objets et expéditeurs des derniers mails Gmail reçus.

    Args:
        nombre: le nombre de mails à lire (5 par défaut)
    """
    try:
        service = obtenir_service_gmail()
        resultats = service.users().messages().list(
            userId="me", maxResults=nombre, labelIds=["INBOX"]
        ).execute()
        messages = resultats.get("messages", [])
        if not messages:
            return "Ta boîte de réception est vide."

        lignes = []
        for i, message in enumerate(messages, 1):
            detail = service.users().messages().get(
                userId="me", id=message["id"], format="metadata",
                metadataHeaders=["From", "Subject"],
            ).execute()
            entetes = {h["name"]: h["value"] for h in detail.get("payload", {}).get("headers", [])}
            lignes.append(f"{i}. De {entetes.get('From', 'Inconnu')} — {entetes.get('Subject', '(sans sujet)')}")
        return "\n".join(lignes)
    except Exception as erreur:
        msg = str(erreur)
        if "access_denied" in msg or "403" in msg:
            return (
                "Google bloque Gmail (mode test). "
                "Ajoute lutreaumaxens@gmail.com en utilisateur test, "
                "puis dis « connecte Gmail »."
            )
        return f"Je n'ai pas réussi à lire tes mails : {erreur}"
