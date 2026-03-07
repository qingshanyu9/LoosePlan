from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Dict, Tuple

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal, Slot


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class GlobalHotkeyService(QObject, QAbstractNativeEventFilter):
    showOrb = Signal()
    openChat = Signal()
    openSchedule = Signal()
    toastRequested = Signal(str)

    def __init__(self, parent: QObject | None = None):
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._user32 = ctypes.windll.user32
        self._registered: Dict[int, Tuple[int, int]] = {}
        self._enabled = False

    def _register(self, hotkey_id: int, modifiers: int, vk: int) -> bool:
        ok = bool(self._user32.RegisterHotKey(None, hotkey_id, modifiers, vk))
        if ok:
            self._registered[hotkey_id] = (modifiers, vk)
        return ok

    @Slot()
    def start(self) -> None:
        if self._enabled:
            return
        mods = MOD_ALT | MOD_SHIFT | MOD_NOREPEAT
        failed: list[str] = []
        if not self._register(1, mods, ord("L")):
            failed.append("Alt+Shift+L")
        if not self._register(2, mods, ord("C")):
            failed.append("Alt+Shift+C")
        if not self._register(3, mods, ord("S")):
            failed.append("Alt+Shift+S")
        self._enabled = True
        if failed:
            self.toastRequested.emit("快捷键注册失败：" + ", ".join(failed))

    @Slot()
    def stop(self) -> None:
        for hotkey_id in list(self._registered.keys()):
            try:
                self._user32.UnregisterHotKey(None, hotkey_id)
            except Exception:
                pass
        self._registered.clear()
        self._enabled = False

    def nativeEventFilter(self, eventType, message):
        try:
            msg = MSG.from_address(int(message))
            if msg.message != WM_HOTKEY:
                return False, 0
            hid = int(msg.wParam)
            if hid == 1:
                self.showOrb.emit()
                return True, 0
            if hid == 2:
                self.openChat.emit()
                return True, 0
            if hid == 3:
                self.openSchedule.emit()
                return True, 0
        except Exception:
            return False, 0
        return False, 0
