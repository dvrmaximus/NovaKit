"""Helpers Win32 — multi-écran, overlay, raccourcis globaux."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

TRANSPARENT_KEY = "#010203"
TRANSPARENT_KEY_RGB = (0x01, 0x02, 0x03)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
LWA_ALPHA = 0x2
GA_ROOT = 2
HWND_BOTTOM = 1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
MONITORINFOF_PRIMARY = 0x00000001

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def hwnd_toplevel(widget) -> int:
    wid = int(widget.winfo_id())
    root = user32.GetAncestor(wid, GA_ROOT)
    return int(root or wid)


def _get_exstyle(hwnd: int) -> int:
    return int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))


def _set_exstyle(hwnd: int, style: int) -> None:
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def set_window_alpha(hwnd: int, alpha: int = 230) -> None:
    style = _get_exstyle(hwnd) | WS_EX_LAYERED
    style &= ~WS_EX_TOOLWINDOW
    _set_exstyle(hwnd, style)
    user32.SetLayeredWindowAttributes(hwnd, 0, max(30, min(255, alpha)), LWA_ALPHA)


def bring_to_front(hwnd: int) -> None:
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.ShowWindow(hwnd, 5)


def set_click_through(hwnd: int, enabled: bool) -> None:
    style = _get_exstyle(hwnd) | WS_EX_LAYERED
    if enabled:
        style |= WS_EX_TRANSPARENT
    else:
        style &= ~WS_EX_TRANSPARENT
    _set_exstyle(hwnd, style)


def ensure_interactive(hwnd: int, alpha: int = 235) -> None:
    style = _get_exstyle(hwnd) | WS_EX_LAYERED
    style &= ~WS_EX_TRANSPARENT
    style &= ~WS_EX_NOACTIVATE
    _set_exstyle(hwnd, style)
    user32.SetLayeredWindowAttributes(hwnd, 0, max(30, min(255, alpha)), LWA_ALPHA)
    bring_to_front(hwnd)


def send_to_desktop_layer(hwnd: int) -> None:
    user32.SetWindowPos(
        hwnd, HWND_BOTTOM, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def list_monitors() -> list[dict]:
    """Liste les écrans : left, top, width, height, primary."""
    monitors: list[dict] = []

    def _cb(hmon, _hdc, _rect, _lp):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            monitors.append({
                "left": int(r.left),
                "top": int(r.top),
                "width": int(r.right - r.left),
                "height": int(r.bottom - r.top),
                "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
            })
        return True

    cb = MONITORENUMPROC(_cb)
    user32.EnumDisplayMonitors(0, 0, cb, 0)
    if not monitors:
        w, h = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
        monitors.append({"left": 0, "top": 0, "width": w, "height": h, "primary": True})
    # Primaire d'abord, puis les autres (ordre stable)
    monitors.sort(key=lambda m: (not m["primary"], m["left"], m["top"]))
    return monitors


def resolve_monitor(choice: str | int | None = None) -> dict:
    """
    choice: 1 / 2 / 'primary' / 'secondary' / 'other'
    Par défaut : secondary s'il existe, sinon primary.
    """
    mons = list_monitors()
    if not mons:
        return {"left": 0, "top": 0, "width": 1920, "height": 1080, "primary": True}

    raw = "secondary" if choice is None or choice == "" else str(choice).strip().lower()

    if raw in ("secondary", "other", "autre", "2nd"):
        for m in mons:
            if not m["primary"]:
                return m
        return mons[-1] if len(mons) > 1 else mons[0]

    if raw in ("primary", "main", "1st"):
        for m in mons:
            if m["primary"]:
                return m
        return mons[0]

    try:
        idx = int(raw)
        if 1 <= idx <= len(mons):
            return mons[idx - 1]
    except ValueError:
        pass

    return mons[0]


def screen_size(monitor: dict | None = None) -> tuple[int, int]:
    m = monitor or resolve_monitor()
    return int(m["width"]), int(m["height"])


def screen_geometry(monitor: dict | None = None) -> str:
    """Chaîne Tk geometry : WIDTHxHEIGHT+LEFT+TOP"""
    m = monitor or resolve_monitor()
    return f"{m['width']}x{m['height']}+{m['left']}+{m['top']}"


class HotkeyListener:
    """
    Raccourcis globaux robustes :
    - RegisterHotKey(F8) si possible
    - + polling GetAsyncKeyState (F8 / Ctrl+Shift+A) en secours
    Le polling ne s'arrête JAMAIS tant que unregister() n'est pas appelé.
    """

    MOD_NOREPEAT = 0x4000
    MOD_NONE = 0
    WM_HOTKEY = 0x0312
    VK_CONTROL = 0x11
    VK_SHIFT = 0x10
    VK_A = 0x41
    VK_F8 = 0x77
    HOTKEY_ID_F8 = 0x4158  # 'AX'

    def __init__(self, root, callback, hwnd: int | None = None, **_ignored):
        self.root = root
        self.callback = callback
        self._held = False
        self._ok = True
        self._hwnd_hotkey = hwnd or None
        self._registered = bool(
            user32.RegisterHotKey(
                self._hwnd_hotkey, self.HOTKEY_ID_F8, self.MOD_NOREPEAT, self.VK_F8
            )
        )
        self.root.after(40, self._poll)

    @property
    def registered(self) -> bool:
        return self._ok

    @staticmethod
    def _down(vk: int) -> bool:
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def _fire(self):
        try:
            self.callback()
        except Exception:
            pass

    def _combo_active(self) -> bool:
        if self._down(self.VK_F8):
            return True
        return (
            self._down(self.VK_CONTROL)
            and self._down(self.VK_SHIFT)
            and self._down(self.VK_A)
        )

    def _poll(self):
        if not self._ok:
            return
        try:
            # Messages RegisterHotKey
            msg = wintypes.MSG()
            while user32.PeekMessageW(
                ctypes.byref(msg), self._hwnd_hotkey, self.WM_HOTKEY, self.WM_HOTKEY, 1
            ):
                if msg.wParam == self.HOTKEY_ID_F8:
                    self._fire()
                    self._held = True

            active = self._combo_active()
            if active and not self._held:
                self._held = True
                self._fire()
            elif not active:
                self._held = False
        except Exception:
            pass
        try:
            self.root.after(40, self._poll)
        except Exception:
            self._ok = False

    def unregister(self):
        self._ok = False
        if self._registered:
            try:
                user32.UnregisterHotKey(self._hwnd_hotkey, self.HOTKEY_ID_F8)
            except Exception:
                pass
            self._registered = False
