from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import DATA_DIR, NOM_IA, NOM_IA_AFFICHE, REMOTE_PIN, REMOTE_PORT
from core.hub import AstatHub
from remote import state
from remote.network import obtenir_ip_wifi
from remote.screen import (
    capturer_jpeg,
    choisir_ecran,
    client_connecte,
    client_deconnecte,
    ecran_actuel,
    frame_actuelle,
    geometrie_ecran_actif,
    lister_ecrans,
    regler_qualite,
)
from remote.audio import (
    audio_config,
    audio_disponible,
    chunk_actuel,
    client_audio_connecte,
    client_audio_deconnecte,
)
from tools.pc_control import SCREENSHOT_DIR

app = FastAPI(title=f"{NOM_IA} Remote", docs_url=None, redoc_url=None)
hub = AstatHub.get()

STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


def _verifier_pin(pin: Optional[str]):
    if not pin or pin != REMOTE_PIN:
        raise HTTPException(status_code=401, detail="PIN incorrect")


class CommandBody(BaseModel):
    message: str


class PinBody(BaseModel):
    pin: str


@app.get("/health")
async def health():
    return {"ok": True, "assistant": NOM_IA, "online": True}


@app.get("/api/profile")
async def profile():
    return {"name": NOM_IA, "display": NOM_IA_AFFICHE}


@app.get("/", response_class=HTMLResponse)
async def mobile_ui():
    html = (STATIC / "mobile.html").read_text(encoding="utf-8")
    return html.replace("{{NOM_IA}}", NOM_IA).replace("{{NOM_IA_AFFICHE}}", NOM_IA_AFFICHE)


@app.post("/api/auth")
async def auth(body: PinBody):
    if body.pin == REMOTE_PIN:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="PIN incorrect")


@app.get("/api/status")
async def status(x_astat_pin: str = Header(default="")):
    _verifier_pin(x_astat_pin)
    ip = obtenir_ip_wifi()
    try:
        import psutil
        cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    except ImportError:
        cpu, ram = None, None
    return {
        "ip": ip,
        "port": REMOTE_PORT,
        "url": state.local_url or f"http://{ip}:{REMOTE_PORT}",
        "public_url": state.public_url,
        "tunnel_actif": state.tunnel_actif,
        "cpu": cpu,
        "ram": ram,
        "clients": hub.remote_clients,
        "name": NOM_IA,
        "display": NOM_IA_AFFICHE,
    }


@app.post("/api/command")
async def command(body: CommandBody, x_astat_pin: str = Header(default="")):
    _verifier_pin(x_astat_pin)
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message vide")
    texte = hub.process(body.message.strip(), source="mobile")
    return {"response": texte}


@app.post("/api/action/{action}")
async def quick_action(action: str, x_astat_pin: str = Header(default="")):
    _verifier_pin(x_astat_pin)
    actions = {
        "lock": "Verrouille l'écran",
        "sleep": "Mets le PC en veille",
        "screenshot": "Prends une capture d'écran",
        "cancel_shutdown": "Annule l'extinction",
        "volume_up": "Augmente le volume de 20",
        "volume_down": "Diminue le volume de 20",
        "pause": "Pause la musique",
        "next": "Piste suivante",
        "prev": "Piste précédente",
    }
    msg = actions.get(action)
    if not msg:
        raise HTTPException(status_code=404, detail="Action inconnue")
    texte = hub.process(msg, source="mobile")
    return {"response": texte}


@app.get("/api/screens")
async def screens(pin: str = Query(default=""), x_astat_pin: str = Header(default="")):
    """Liste les écrans + celui actuellement streamé."""
    _verifier_pin(pin or x_astat_pin)
    return {
        "screens": lister_ecrans(),
        "current": ecran_actuel(),
    }


class SelectScreenBody(BaseModel):
    index: int = 1


@app.post("/api/screen/select")
async def screen_select(body: SelectScreenBody, x_astat_pin: str = Header(default="")):
    """Change l'écran streamé (1, 2, …)."""
    _verifier_pin(x_astat_pin)
    try:
        info = choisir_ecran(int(body.index))
        return {"ok": True, "current": info}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/screenshot")
async def screenshot(pin: str = Query(default=""), x_astat_pin: str = Header(default="")):
    _verifier_pin(pin or x_astat_pin)
    chemin = SCREENSHOT_DIR / "latest.png"
    if not chemin.exists():
        try:
            capturer_jpeg()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        chemin = SCREENSHOT_DIR / "latest.png"
    if not chemin.exists():
        raise HTTPException(status_code=404, detail="Pas de capture")
    return FileResponse(chemin, media_type="image/png")


@app.get("/api/screen/live")
async def screen_live(
    pin: str = Query(default=""),
    x_astat_pin: str = Header(default=""),
    q: int = Query(default=42, ge=20, le=85),
):
    """Frame JPEG unique (fallback). Préférer /ws/screen pour 30 FPS."""
    _verifier_pin(pin or x_astat_pin)
    try:
        data = capturer_jpeg(qualite=q, largeur_max=960)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Capture impossible : {exc}") from exc
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@app.websocket("/ws/screen")
async def screen_stream(ws: WebSocket):
    """Flux binaire JPEG ~30 FPS vers le téléphone."""
    import asyncio

    await ws.accept()
    pin = ws.query_params.get("pin", "")
    if pin != REMOTE_PIN:
        await ws.close(code=4001)
        return

    try:
        fps = int(ws.query_params.get("fps", "30"))
    except ValueError:
        fps = 30
    fps = max(15, min(30, fps))
    interval = 1.0 / fps
    mode = ws.query_params.get("q", "eco")
    regler_qualite("hq" if mode == "hq" else "eco")

    client_connecte()
    for _ in range(80):
        if frame_actuelle():
            break
        await asyncio.sleep(0.02)

    try:
        while True:
            t0 = asyncio.get_event_loop().time()
            data = frame_actuelle()
            if data:
                await ws.send_bytes(data)
            elapsed = asyncio.get_event_loop().time() - t0
            await asyncio.sleep(max(0.0, interval - elapsed))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        client_deconnecte()


@app.get("/api/audio/status")
async def audio_status(pin: str = Query(default=""), x_astat_pin: str = Header(default="")):
    _verifier_pin(pin or x_astat_pin)
    return audio_config()


@app.websocket("/ws/audio")
async def audio_stream(ws: WebSocket):
    """Flux PCM s16le mono 24 kHz (son du PC → téléphone)."""
    import asyncio
    import json

    await ws.accept()
    pin = ws.query_params.get("pin", "")
    if pin != REMOTE_PIN:
        await ws.close(code=4001)
        return

    if not audio_disponible():
        await ws.send_text(json.dumps({
            "type": "error",
            "message": "Audio indisponible — pip install soundcard numpy",
        }))
        await ws.close(code=4002)
        return

    cfg = audio_config()
    await ws.send_text(json.dumps({"type": "audio_config", **cfg}))
    client_audio_connecte()
    try:
        # Laisse démarrer la capture
        await asyncio.sleep(0.15)
        empty = 0
        while True:
            data = chunk_actuel()
            if data:
                empty = 0
                await ws.send_bytes(data)
            else:
                empty += 1
                await asyncio.sleep(0.015 if empty < 20 else 0.04)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        client_audio_deconnecte()


class ClickBody(BaseModel):
    x: float = 0.5
    y: float = 0.5


@app.post("/api/screen/click")
async def screen_click(body: ClickBody, x_astat_pin: str = Header(default="")):
    """Clic relatif (0-1) sur l'écran actuellement sélectionné."""
    _verifier_pin(x_astat_pin)
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        geo = geometrie_ecran_actif()
        x = max(0.0, min(1.0, float(body.x)))
        y = max(0.0, min(1.0, float(body.y)))
        abs_x = geo["left"] + int(x * (geo["width"] - 1))
        abs_y = geo["top"] + int(y * (geo["height"] - 1))
        pyautogui.click(abs_x, abs_y)
        return {"ok": True, "x": abs_x, "y": abs_y, "screen": geo}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    pin = ws.query_params.get("pin", "")
    if pin != REMOTE_PIN:
        await ws.close(code=4001)
        return

    hub.remote_clients += 1
    try:
        await ws.send_json({"type": "connected", "message": f"Connecté à {NOM_IA}."})
        while True:
            data = await ws.receive_json()
            msg = data.get("message", "").strip()
            if not msg:
                continue
            await ws.send_json({"type": "user", "message": msg})
            reponse = hub.process(msg, source="mobile")
            await ws.send_json({"type": "astat", "message": reponse})
    except WebSocketDisconnect:
        pass
    finally:
        hub.remote_clients = max(0, hub.remote_clients - 1)


def _port_libre(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _fixer_stdio_pythonw():
    """pythonw n'a pas de console : stdout/stderr sont None → uvicorn plante."""
    import sys
    if sys.stdout is None:
        sys.stdout = open(DATA_DIR / "stdout.log", "a", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(DATA_DIR / "stderr.log", "a", encoding="utf-8")


def demarrer_serveur():
    import traceback

    from remote.network import obtenir_ip_wifi, ouvrir_parefeu

    log = DATA_DIR / "serveur.log"
    try:
        _fixer_stdio_pythonw()

        port = REMOTE_PORT
        if not _port_libre(port):
            for candidat in range(REMOTE_PORT + 1, REMOTE_PORT + 15):
                if _port_libre(candidat):
                    port = candidat
                    break
            else:
                raise OSError(f"Aucun port libre entre {REMOTE_PORT} et {REMOTE_PORT + 14}")

        state.port_actif = port
        state.local_url = f"http://{obtenir_ip_wifi()}:{port}"
        ouvrir_parefeu(port)

        import uvicorn
        # log_config=None évite le ColorFormatter qui appelle isatty()
        config = uvicorn.Config(
            app, host="0.0.0.0", port=port,
            log_level="warning", access_log=False, log_config=None,
        )
        log.write_text(f"Serveur demarre sur le port {port}\n", encoding="utf-8")
        uvicorn.Server(config).run()
    except Exception:
        state.serveur_erreur = traceback.format_exc(limit=3)
        log.write_text(traceback.format_exc(), encoding="utf-8")
