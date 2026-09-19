"""API + panel admin NovaKit (port 8788)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from online.db import (
    add_install,
    change_password,
    create_session,
    drop_session,
    ensure_admin,
    list_installs,
    session_ok,
    stats,
    verify_admin,
)

STATIC = Path(__file__).resolve().parent / "static"
COOKIE = "novakit_admin"
PORT = 8788

app = FastAPI(title="NovaKit Online", docs_url=None, redoc_url=None)
ensure_admin()


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
    nom_ia: str = "?"
    ville: str = ""
    os: str = ""
    pc: str = ""


def _token(request: Request) -> str | None:
    return request.cookies.get(COOKIE) or request.headers.get("X-Admin-Token")


def _require_admin(request: Request) -> None:
    if not session_ok(_token(request)):
        raise HTTPException(401, "Non authentifié")


@app.get("/")
def home():
    return FileResponse(STATIC / "admin.html")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "novakit-online"}


@app.post("/api/register")
def register(body: RegisterBody):
    """Endpoint public — appelé par chaque install NovaKit."""
    data = body.model_dump()
    iid = add_install(data)
    return {"ok": True, "id": iid}


@app.post("/api/admin/login")
def login(body: LoginBody, response: Response):
    if not verify_admin(body.username.strip(), body.password):
        raise HTTPException(401, "Identifiants incorrects")
    token = create_session()
    response = JSONResponse({"ok": True, "username": body.username.strip()})
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
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
    return {"ok": True, **stats()}


@app.get("/api/admin/installs")
def installs(request: Request):
    _require_admin(request)
    return {"ok": True, "items": list_installs()}


@app.post("/api/admin/password")
def password(body: PasswordBody, request: Request):
    _require_admin(request)
    if not change_password(body.username.strip(), body.old_password, body.new_password):
        raise HTTPException(400, "Impossible de changer le mot de passe")
    return {"ok": True}


if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
