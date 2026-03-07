# app/services/window_manager.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent


@dataclass
class _WinEntry:
    qml_file: str
    obj: QObject


class WindowManager(QObject):
    """Create/raise QML top-level windows and ensure single-instance per key."""

    toastRequested = Signal(str)

    def __init__(self, *, engine: QQmlApplicationEngine, pages_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._engine = engine
        self._pages_dir = Path(pages_dir).resolve()
        self._wins: dict[str, _WinEntry] = {}

    def _emit_toast(self, msg: str) -> None:
        s = (msg or "").strip()
        if s:
            self.toastRequested.emit(s)

    def _create_window(self, qml_file: str) -> Optional[QObject]:
        qml_path = (self._pages_dir / qml_file).resolve()
        if not qml_path.exists():
            self._emit_toast(f"找不到页面：{qml_file}")
            return None

        comp = QQmlComponent(self._engine, QUrl.fromLocalFile(str(qml_path)))
        if comp.status() != QQmlComponent.Ready:
            try:
                self._emit_toast(comp.errorString())
            except Exception:
                self._emit_toast("页面加载失败")
            return None

        try:
            obj = comp.create()
        except Exception as e:
            self._emit_toast(f"页面创建失败：{e}")
            return None

        if obj is None:
            self._emit_toast("页面创建失败")
            return None

        return obj

    def _show_and_raise(self, obj: QObject) -> None:
        try:
            obj.setProperty("visible", True)
        except Exception:
            pass
        try:
            if hasattr(obj, "show"):
                obj.show()
        except Exception:
            pass
        try:
            if hasattr(obj, "raise_"):
                obj.raise_()
        except Exception:
            pass
        try:
            if hasattr(obj, "requestActivate"):
                obj.requestActivate()
        except Exception:
            pass

    @Slot(str)
    def closeWindow(self, key: str) -> None:
        entry = self._wins.get(str(key))
        if not entry:
            return
        obj = entry.obj
        try:
            if hasattr(obj, "close"):
                obj.close()
        except Exception:
            pass

    @Slot(str, str)
    def openPage(self, key: str, qml_file: str) -> None:
        """QML-callable: open a page and ensure single window for the given key."""
        self.open_or_replace(key=str(key), qml_file=str(qml_file))

    def open_or_replace(self, *, key: str, qml_file: str, props: Optional[dict[str, Any]] = None) -> Optional[QObject]:
        key = str(key)
        qml_file = str(qml_file)

        entry = self._wins.get(key)
        if entry is not None and entry.qml_file != qml_file:
            old_obj = entry.obj
            try:
                if hasattr(old_obj, "close"):
                    old_obj.close()
            except Exception:
                pass
            current = self._wins.get(key)
            if current is not None and current.obj is old_obj:
                self._wins.pop(key, None)
            entry = None

        if entry is None:
            obj = self._create_window(qml_file)
            if obj is None:
                return None

            self._wins[key] = _WinEntry(qml_file=qml_file, obj=obj)

            def _on_destroyed(*_args: object, _key: str = key, _obj: QObject = obj) -> None:
                current = self._wins.get(_key)
                if current is not None and current.obj is _obj:
                    self._wins.pop(_key, None)

            try:
                obj.destroyed.connect(_on_destroyed)
            except Exception:
                pass

            entry = self._wins.get(key)
        else:
            try:
                entry.obj.metaObject()
            except Exception:
                self._wins.pop(key, None)
                return self.open_or_replace(key=key, qml_file=qml_file, props=props)

        obj = entry.obj

        if props:
            for k, v in props.items():
                try:
                    obj.setProperty(str(k), v)
                except Exception:
                    pass

        try:
            visible = bool(obj.property("visible"))
        except Exception:
            visible = False
        if visible:
            self._emit_toast("窗口已打开")

        self._show_and_raise(obj)
        return obj
