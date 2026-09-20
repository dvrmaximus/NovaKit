"""API + panel admin NovaKit (port 8788)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from online.db import (
    add_install,
    change_password,
    create_session,
    drop_session,
    enqueue_command,
    ensure_admin,
    get_install,
    importer_journal_local,
    list_installs,
    pop_commands,
    session_ok,
    stats,
    touch_client,
    verify_admin,
)

STATIC = Path(__file__).resolve().parent / "static"
COOKIE = "novakit_admin"
PORT = 8788

app = FastAPI(title="NovaKit Online", docs_url=None, redoc_url=None)
# Compte DB sans fichier credentials (le fichier = mode créateur UI)
ensure_admin(ecrire_fichier=False)

ACTIONS_OK = {"message", "speak", "ping", "status"}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PasswordBody(BaseModel):
    username: str
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


class RegisterBody(BaseModel):
    kit: str = "NovaKit"
    version: str = ""
    event: str = "inscription"
    when: str = ""
    pseudo: str = "Anonyme"
    email: str = ""
    nom_ia: str = "?"
    ville: str = ""
    os: str = ""
    pc: str = ""
    client_id: str = ""
    ip: str = ""
    ip_local: str = ""
    ip_public: str = ""
    user_agent: str = ""
    online: bool = True


class HeartbeatBody(BaseModel):
    client_id: str
    pseudo: str = ""
    email: str = ""
    nom_ia: str = ""
    ville: str = ""
    version: str = ""
    ip: str = ""
    ip_local: str = ""
    ip_public: str = ""
    online: bool = True


class CommandBody(BaseModel):
    install_id: int | None = None
    client_id: str = ""
    action: str
    text: str = ""


def _token(request: Request) -> str | None:
    return request.cookies.get(COOKIE) or request.headers.get("X-Admin-Token")


def _require_admin(request: Request) -> None:
    if not session_ok(_token(request)):
        raise HTTPException(401, "Non authentifié")


def _client_ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if fwd:
        return fwd[:64]
    if request.client:
        return (request.client.host or "")[:64]
    return ""


@app.get("/")
def home():
    return FileResponse(STATIC / "admin.html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "novakit-online"}


@app.post("/api/register")
def register(body: RegisterBody, request: Request):
    data = body.model_dump()
    rip = _client_ip(request)
    if rip and not data.get("ip_public"):
        data["ip_public"] = rip
    if rip and not data.get("ip"):
        data["ip"] = rip
    data["user_agent"] = data.get("user_agent") or (request.headers.get("user-agent") or "")[:200]
    iid = add_install(data)
    return {"ok": True, "id": iid, "client_id": data.get("client_id") or ""}


@app.post("/api/client/heartbeat")
def client_heartbeat(body: HeartbeatBody, request: Request):
    data = body.model_dump()
    rip = _client_ip(request)
    if rip:
        data["ip"] = data.get("ip") or rip
        data["ip_public"] = data.get("ip_public") or rip
    add_install({**data, "kit": "NovaKit", "when": "", "event": "heartbeat"})
    touch_client(body.client_id, data)
    return {"ok": True}


@app.get("/api/client/commands")
def client_commands(client_id: str = Query(...)):
    if not client_id.strip():
        raise HTTPException(400, "client_id requis")
    touch_client(client_id.strip(), {})
    return {"ok": True, "commands": pop_commands(client_id.strip())}


@app.post("/api/admin/login")
def login(body: LoginBody, response: Response):
    if not verify_admin(body.username.strip(), body.password):
        raise HTTPException(401, "Identifiants incorrects")
    token = create_session()
    response = JSONResponse({"ok": True, "username": body.username.strip()})
    response.set_cookie(
        COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7, path="/"
    )
    return response


@app.post("/api/admin/logout")
def logout(request: Request, response: Response):
    drop_session(_token(request))
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE)
    return response


@app.get("/api/admin/me")
def me(request: Request):
    _require_admin(request)
    try:
        importer_journal_local()
    except Exception:
        pass
    return {"ok": True, **stats()}


@app.get("/api/admin/installs")
def installs(request: Request):
    _require_admin(request)
    return {"ok": True, "items": list_installs()}


@app.get("/api/admin/installs/{install_id}")
def install_detail(install_id: int, request: Request):
    _require_admin(request)
    row = get_install(install_id)
    if not row:
        raise HTTPException(404, "Introuvable")
    return {"ok": True, "item": row}


@app.post("/api/admin/command")
def admin_command(body: CommandBody, request: Request):
    _require_admin(request)
    action = (body.action or "").strip().lower()
    if action not in ACTIONS_OK:
        raise HTTPException(400, f"Action interdite. OK: {', '.join(sorted(ACTIONS_OK))}")
    client_id = (body.client_id or "").strip()
    install_id = body.install_id
    if install_id and not client_id:
        row = get_install(install_id)
        if not row:
            raise HTTPException(404, "Utilisateur introuvable")
        client_id = (row.get("client_id") or "").strip()
    if not client_id:
        raise HTTPException(400, "Pas de client_id — l'utilisateur doit avoir NovaKit récent en ligne")
    cid = enqueue_command(
        client_id,
        action,
        {"text": (body.text or "")[:500]},
        install_id=install_id,
    )
    return {"ok": True, "command_id": cid, "client_id": client_id, "action": action}


@app.post("/api/admin/password")
def password(body: PasswordBody, request: Request):
    _require_admin(request)
    if not change_password(body.username.strip(), body.old_password, body.new_password):
        raise HTTPException(400, "Impossible de changer le mot de passe")
    return {"ok": True}


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
