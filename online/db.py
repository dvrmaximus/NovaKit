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


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000
    ).hex()


def ensure_admin(username: str = "Lutre", password: str | None = None) -> tuple[str, str, bool]:
    """
    Crée le compte admin s'il n'existe pas.
    Retourne (username, password_clair_si_nouveau_sinon_vide, created).
    """
    init_db()
    with _conn() as c:
        row = c.execute("SELECT username FROM admin WHERE id = 1").fetchone()
        if row:
            return row["username"], "", False

        pwd = password or secrets.token_urlsafe(10)
        salt = secrets.token_hex(16)
        ph = _hash_password(pwd, salt)
        c.execute(
            "INSERT INTO admin (id, username, password_hash, salt, created_at) VALUES (1,?,?,?,?)",
            (username, ph, salt, time.time()),
        )
        CREDS_FILE.write_text(
            f"NovaKit — Compte admin\n"
            f"======================\n\n"
            f"Utilisateur : {username}\n"
            f"Mot de passe : {pwd}\n\n"
            f"Change-le depuis le panel si tu veux.\n"
            f"Ne partage PAS ce fichier.\n",
            encoding="utf-8",
        )
        return username, pwd, True


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
    salt = secrets.token_hex(16)
    ph = _hash_password(new, salt)
    with _conn() as c:
        c.execute(
            "UPDATE admin SET username=?, password_hash=?, salt=? WHERE id=1",
            (username, ph, salt),
        )
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


def add_install(data: dict) -> int:
    init_db()
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO installs
            (pseudo, nom_ia, ville, os, pc, kit, version, when_utc, raw_json, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                (data.get("pseudo") or "")[:64],
                (data.get("nom_ia") or "")[:64],
                (data.get("ville") or "")[:64],
                (data.get("os") or "")[:32],
                (data.get("pc") or "")[:64],
                (data.get("kit") or "NovaKit")[:32],
                (data.get("version") or "")[:16],
                (data.get("when") or "")[:64],
                json.dumps(data, ensure_ascii=False),
                time.time(),
            ),
        )
        return int(cur.lastrowid)


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
        last = c.execute(
            "SELECT pseudo, nom_ia, when_utc FROM installs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return {
        "total": total,
        "dernier": dict(last) if last else None,
    }
