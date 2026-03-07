from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QCursor, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from app.core.app_paths import default_user_data_dir

from .data_transfer import DataTransfer
from .window_manager import WindowManager


class TrayManager(QObject):
    def __init__(
        self,
        *,
        app: QApplication,
        icon: QIcon,
        window_mgr: WindowManager,
        data_transfer: DataTransfer,
        runtime: QObject,
        project_root: Path,
        draft: QObject,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._app = app
        self._wm = window_mgr
        self._data = data_transfer
        self._runtime = runtime
        self._root = Path(project_root).resolve()
        self._draft = draft

        self._tray = QSystemTrayIcon(icon, app)
        self._menu = QMenu()
        self._wire_menu()

        try:
            self._wm.toastRequested.connect(self._show_message)
        except Exception:
            pass
        try:
            self._data.toastRequested.connect(self._show_message)
        except Exception:
            pass

        self._tray.setContextMenu(self._menu)
        self._tray.setToolTip("LoosePlan")
        self._tray.show()

    def _show_message(self, text: str) -> None:
        s = (text or "").strip()
        if not s:
            return
        try:
            self._tray.showMessage("LoosePlan", s, QSystemTrayIcon.Information, 2500)
        except Exception:
            pass

    @Slot(str)
    def showInfo(self, text: str) -> None:
        self._show_message(text)

    @Slot()
    def popupMenuAtCursor(self) -> None:
        try:
            self._menu.popup(QCursor.pos())
        except Exception:
            pass

    @Slot()
    def openChat(self) -> None:
        self._guard_or_open("chat", "chat.qml")

    @Slot()
    def openSchedule(self) -> None:
        self._guard_or_open("schedule", "schedule.qml")

    def _onboarding_in_progress(self) -> bool:
        return (self._root / ".tmp" / "onboarding_state.json").exists()

    def _has_config(self) -> bool:
        candidates: list[Path] = []
        try:
            last_dir = str(getattr(self._runtime, "lastDataDir") or "").strip()
        except Exception:
            last_dir = ""
        if last_dir:
            candidates.append(Path(last_dir).expanduser())

        try:
            dd = str(getattr(self._draft, "getDraftDataDir")() or "").strip()
        except Exception:
            dd = ""
        if dd:
            candidates.append(Path(dd).expanduser())

        candidates.append(default_user_data_dir(self._root))

        for d in candidates:
            try:
                p = d.resolve() / "config.json"
                if p.exists():
                    try:
                        setattr(self._runtime, "lastDataDir", str(d.resolve()))
                    except Exception:
                        pass
                    return True
            except Exception:
                continue
        return False

    def _open_onboarding_resume(self) -> None:
        step = 1
        try:
            step = int(getattr(self._draft, "getDraftStep")() or 1)
        except Exception:
            step = 1
        mapping = {
            1: "onboarding_1_data_dir.qml",
            2: "onboarding_2_kimi.qml",
            3: "onboarding_3_feishu.qml",
            4: "onboarding_4_naming.qml",
            5: "onboarding_5_quiz.qml",
            6: "onboarding_6_profile_result.qml",
        }
        self._wm.open_or_replace(key="onboarding", qml_file=mapping.get(step, "onboarding_1_data_dir.qml"))

    def _guard_or_open(self, key: str, qml_file: str) -> None:
        if not self._has_config():
            self._show_message("请先完成初始化配置")
            self._open_onboarding_resume()
            return
        self._wm.open_or_replace(key=key, qml_file=qml_file)

    def _wire_menu(self) -> None:
        act_chat = QAction("聊天", self._menu)
        act_schedule = QAction("日程", self._menu)
        act_memory = QAction("记忆图谱", self._menu)
        act_weekly = QAction("每周回顾", self._menu)
        act_settings = QAction("设置", self._menu)
        act_import = QAction("导入", self._menu)
        act_export = QAction("导出", self._menu)
        act_exit = QAction("退出", self._menu)

        act_chat.triggered.connect(lambda: self._guard_or_open("chat", "chat.qml"))
        act_schedule.triggered.connect(lambda: self._guard_or_open("schedule", "schedule.qml"))
        act_memory.triggered.connect(lambda: self._guard_or_open("memory_graph", "memory_graph.qml"))
        act_weekly.triggered.connect(lambda: self._guard_or_open("weekly_review", "weekly_review.qml"))
        act_settings.triggered.connect(lambda: self._guard_or_open("settings", "settings.qml"))
        act_import.triggered.connect(self._data.import_zip)
        act_export.triggered.connect(self._data.export_zip)
        act_exit.triggered.connect(self._app.quit)

        self._menu.addAction(act_exit)
        self._menu.addSeparator()
        self._menu.addAction(act_import)
        self._menu.addAction(act_export)
        self._menu.addSeparator()
        self._menu.addAction(act_chat)
        self._menu.addAction(act_schedule)
        self._menu.addAction(act_memory)
        self._menu.addAction(act_weekly)
        self._menu.addAction(act_settings)
