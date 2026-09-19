# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller â€” NovaKit application Windows."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None
root = Path(SPECPATH)

datas = [
    (str(root / "remote" / "static"), "remote/static"),
    (str(root / "creator.json"), "."),
    (str(root / "version.json"), "."),
    (str(root / ".env.example"), "."),
    (str(root / "assets" / "novakit.ico"), "assets"),
    (str(root / "README.md"), "."),
]

hiddenimports = [
    "customtkinter",
    "edge_tts",
    "pygame",
    "speech_recognition",
    "google.genai",
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "starlette",
    "multipart",
    "PIL",
    "mss",
    "soundcard",
    "numpy",
    "pyautogui",
    "pyperclip",
    "pyngrok",
    "dotenv",
]

for pkg in ("customtkinter", "edge_tts"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        hiddenimports += h
    except Exception:
        pass

try:
    datas += collect_data_files("customtkinter")
except Exception:
    pass

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NovaKitDebug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(root / "assets" / "novakit.ico"),
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NovaKitDebug",
)


