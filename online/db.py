"""SQLite : compte admin + inscriptions."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path

from config import DATA_DIR

DB_PATH = DATA_DIR / "online.db"
CREDS_FILE = DATA_DIR / "admin_credentials.txt"
SESSION_TTL = 60 * 60 * 24 * 7  # 7 jours


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS admin (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS installs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pseudo TEXT,
                email TEXT,
                nom_ia TEXT,
                ville TEXT,
                os TEXT,
                pc TEXT,
                kit TEXT,
                version TEXT,
                when_utc TEXT,
                raw_json TEXT,
                created_at REAL NOT NULL
            );
            """
        )
        # Migration douce colonnes installs
        cols = {r[1] for r in c.execute("PRAGMA table_info(installs)").fetchall()}
        for col, typ in (
            ("email", "TEXT"),
            ("ip", "TEXT"),
            ("ip_local", "TEXT"),
            ("ip_public", "TEXT"),
            ("client_id", "TEXT"),
            ("user_agent", "TEXT"),
            ("last_seen", "REAL"),
            ("online", "INTEGER DEFAULT 0"),
        ):
            if col not in cols:
                c.execute(f"ALTER TABLE installs ADD COLUMN {col} {typ}")

        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                install_id INTEGER,
                action TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at REAL NOT NULL,
                done_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_commands_client ON commands(client_id, status);
            """
        )


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


def ensure_admin(
    username: str = "Lutre",
    password: str | None = None,
    *,
    ecrire_fichier: bool = False,
) -> tuple[str, str, bool]:
    """
    Crée le compte admin s'il n'existe pas.
    Retourne (username, password_clair_si_nouveau_sinon_vide, created).

    ecrire_fichier=True uniquement pour les outils créateur (écrit
    data/admin_credentials.txt — marqueur du mode créateur dans l'UI).
    """
    init_db()
    with _conn() as c:
        row = c.execute("SELECT username FROM admin WHERE id = 1").fetchone()
        if row:
            return row["username"], "", False

        pwd = password or "NovaKitAdmin"
        salt = secrets.token_hex(16)
        ph = _hash_password(pwd, salt)
        c.execute(
            "INSERT INTO admin (id, username, password_hash, salt, created_at) VALUES (1,?,?,?,?)",
            (username, ph, salt, time.time()),
        )
        if ecrire_fichier:
            _ecrire_creds(username, pwd)
        return username, pwd, True


def _ecrire_creds(username: str, password: str) -> None:
    CREDS_FILE.parent.mkdir(exist_ok=True)
    CREDS_FILE.write_text(
        f"NovaKit — Compte admin\n"
        f"======================\n\n"
        f"Utilisateur : {username}\n"
        f"Mot de passe : {password}\n\n"
        f"Panel : http://127.0.0.1:8788\n"
        f"Change-le depuis le panel si tu veux.\n"
        f"Ne partage PAS ce fichier.\n",
        encoding="utf-8",
    )


def set_admin_password(username: str, password: str) -> None:
    """Définit / réinitialise le mot de passe admin (créateur)."""
    init_db()
    salt = secrets.token_hex(16)
    ph = _hash_password(password, salt)
    with _conn() as c:
        row = c.execute("SELECT id FROM admin WHERE id = 1").fetchone()
        if row:
            c.execute(
                "UPDATE admin SET username=?, password_hash=?, salt=? WHERE id=1",
                (username, ph, salt),
            )
        else:
            c.execute(
                "INSERT INTO admin (id, username, password_hash, salt, created_at) VALUES (1,?,?,?,?)",
                (username, ph, salt, time.time()),
            )
    _ecrire_creds(username, password)


def lire_identifiants_fichier() -> tuple[str, str]:
    """Lit user/mdp depuis admin_credentials.txt si possible."""
    if not CREDS_FILE.exists():
        return "Lutre", ""
    user, pwd = "Lutre", ""
    for line in CREDS_FILE.read_text(encoding="utf-8").splitlines():
        if "Utilisateur" in line and ":" in line:
            user = line.split(":", 1)[1].strip() or user
        if "Mot de passe" in line and ":" in line:
            pwd = line.split(":", 1)[1].strip()
    return user, pwd


def verify_admin(username: str, password: str) -> bool:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM admin WHERE id = 1").fetchone()
    if not row:
        return False
    if not hmac.compare_digest(row["username"], username):
        return False
    expect = _hash_password(password, row["salt"])
    return hmac.compare_digest(expect, row["password_hash"])


def change_password(username: str, old: str, new: str) -> bool:
    if not verify_admin(username, old):
        return False
    if len(new) < 6:
        return False
    set_admin_password(username, new)
    return True


def create_session() -> str:
    init_db()
    token = secrets.token_urlsafe(32)
    now = time.time()
    with _conn() as c:
        c.execute(
            "INSERT INTO sessions (token, created_at, expires_at) VALUES (?,?,?)",
            (token, now, now + SESSION_TTL),
        )
        c.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return token


def session_ok(token: str | None) -> bool:
    if not token:
        return False
    init_db()
    now = time.time()
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM sessions WHERE token=? AND expires_at > ?",
            (token, now),
        ).fetchone()
    return bool(row)


def drop_session(token: str | None) -> None:
    if not token:
        return
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


def reset_utilisateurs() -> int:
    """Efface toutes les inscriptions (panel admin)."""
    init_db()
    with _conn() as c:
        n = c.execute("SELECT COUNT(*) AS n FROM installs").fetchone()["n"]
        c.execute("DELETE FROM installs")
        c.execute("DELETE FROM sessions")
    journal = DATA_DIR / "installs_sent.jsonl"
    if journal.exists():
        try:
            journal.write_text("", encoding="utf-8")
        except Exception:
            pass
    return int(n)


def reset_admin_createur(username: str = "Lutre", password: str = "LutreAdmin") -> None:
    """Recrée le compte admin unique du créateur."""
    init_db()
    with _conn() as c:
        c.execute("DELETE FROM admin")
        c.execute("DELETE FROM sessions")
    set_admin_password(username, password)


def add_install(data: dict) -> int:
    """Enregistre ou met à jour un utilisateur (par client_id / email)."""
    init_db()
    client_id = (data.get("client_id") or "")[:64]
    email = (data.get("email") or "")[:120]
    now = time.time()
    with _conn() as c:
        row = None
        if client_id:
            row = c.execute(
                "SELECT id FROM installs WHERE client_id=? ORDER BY id DESC LIMIT 1",
                (client_id,),
            ).fetchone()
        if not row and email:
            row = c.execute(
                "SELECT id FROM installs WHERE LOWER(TRIM(email))=LOWER(TRIM(?)) ORDER BY id DESC LIMIT 1",
                (email,),
            ).fetchone()
        fields = (
            (data.get("pseudo") or "")[:64],
            email,
            (data.get("nom_ia") or "")[:64],
            (data.get("ville") or "")[:64],
            (data.get("os") or "")[:32],
            (data.get("pc") or "")[:64],
            (data.get("kit") or "NovaKit")[:32],
            (data.get("version") or "")[:16],
            (data.get("when") or "")[:64],
            json.dumps(data, ensure_ascii=False),
            (data.get("ip") or data.get("ip_public") or "")[:64],
            (data.get("ip_local") or "")[:64],
            (data.get("ip_public") or "")[:64],
            client_id,
            (data.get("user_agent") or "")[:200],
            now,
            1 if data.get("online") else 0,
        )
        if row:
            c.execute(
                """
                UPDATE installs SET
                  pseudo=?, email=?, nom_ia=?, ville=?, os=?, pc=?, kit=?, version=?,
                  when_utc=?, raw_json=?, ip=?, ip_local=?, ip_public=?, client_id=?,
                  user_agent=?, last_seen=?, online=?
                WHERE id=?
                """,
                (*fields, row["id"]),
            )
            return int(row["id"])
        cur = c.execute(
            """
            INSERT INTO installs
            (pseudo, email, nom_ia, ville, os, pc, kit, version, when_utc, raw_json,
             ip, ip_local, ip_public, client_id, user_agent, last_seen, online, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (*fields, now),
        )
        return int(cur.lastrowid)


def touch_client(client_id: str, extra: dict | None = None) -> None:
    if not client_id:
        return
    init_db()
    extra = extra or {}
    with _conn() as c:
        c.execute(
            """
            UPDATE installs SET last_seen=?, online=1,
              ip=COALESCE(NULLIF(?,''), ip),
              ip_public=COALESCE(NULLIF(?,''), ip_public),
              ip_local=COALESCE(NULLIF(?,''), ip_local),
              version=COALESCE(NULLIF(?,''), version),
              nom_ia=COALESCE(NULLIF(?,''), nom_ia)
            WHERE client_id=?
            """,
            (
                time.time(),
                (extra.get("ip") or extra.get("ip_public") or "")[:64],
                (extra.get("ip_public") or "")[:64],
                (extra.get("ip_local") or "")[:64],
                (extra.get("version") or "")[:16],
                (extra.get("nom_ia") or "")[:64],
                client_id[:64],
            ),
        )


def enqueue_command(client_id: str, action: str, payload: dict | None = None, install_id: int | None = None) -> int:
    init_db()
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO commands (client_id, install_id, action, payload, status, created_at)
            VALUES (?,?,?,?, 'pending', ?)
            """,
            (
                client_id[:64],
                install_id,
                action[:32],
                json.dumps(payload or {}, ensure_ascii=False),
                time.time(),
            ),
        )
        return int(cur.lastrowid)


def pop_commands(client_id: str, limit: int = 10) -> list[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM commands
            WHERE client_id=? AND status='pending'
            ORDER BY id ASC LIMIT ?
            """,
            (client_id[:64], limit),
        ).fetchall()
        out = []
        for r in rows:
            c.execute(
                "UPDATE commands SET status='sent', done_at=? WHERE id=?",
                (time.time(), r["id"]),
            )
            d = dict(r)
            try:
                d["payload"] = json.loads(d.get("payload") or "{}")
            except Exception:
                d["payload"] = {}
            out.append(d)
        return out


def get_install(install_id: int) -> dict | None:
    init_db()
    with _conn() as c:
        row = c.execute("SELECT * FROM installs WHERE id=?", (install_id,)).fetchone()
    return dict(row) if row else None


def list_installs(limit: int = 200) -> list[dict]:
    init_db()
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM installs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    init_db()
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM installs").fetchone()["n"]
        uniques = c.execute(
            """
            SELECT COUNT(DISTINCT LOWER(TRIM(COALESCE(email, '')))) AS n
            FROM installs
            WHERE email IS NOT NULL AND TRIM(email) != ''
            """
        ).fetchone()["n"]
        last = c.execute(
            "SELECT pseudo, email, nom_ia, when_utc FROM installs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "uniques_email": uniques,
        "dernier": dict(last) if last else None,
    }


def importer_journal_local() -> int:
    """Importe data/installs_sent.jsonl dans la base admin (déduplique grossièrement)."""
    journal = DATA_DIR / "installs_sent.jsonl"
    if not journal.exists():
        return 0
    init_db()
    ajoutes = 0
    with journal.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            # skip si déjà même email+pseudo+when
            email = (data.get("email") or "")[:120]
            pseudo = (data.get("pseudo") or "")[:64]
            when = (data.get("when") or "")[:64]
            with _conn() as c:
                exists = c.execute(
                    """
                    SELECT 1 FROM installs
                    WHERE COALESCE(email,'')=? AND COALESCE(pseudo,'')=? AND COALESCE(when_utc,'')=?
                    LIMIT 1
                    """,
                    (email, pseudo, when),
                ).fetchone()
                if exists:
                    continue
            add_install(data)
            ajoutes += 1
    return ajoutes
