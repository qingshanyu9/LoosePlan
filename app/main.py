# app/main.py
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Slot, Property, Signal, QStandardPaths, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from app.core.app_paths import default_user_data_dir


def _project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[1]


def _ensure_sys_path(root: Path) -> None:
    r = str(root)
    if r not in sys.path:
        sys.path.insert(0, r)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _normalize_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


class RuntimeStore(QObject):
    changed = Signal()

    def __init__(self, app_data_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._app_data_dir = app_data_dir
        self._runtime_file = self._app_data_dir / "runtime.json"
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        self._data = _read_json(self._runtime_file)
        self.changed.emit()

    def save(self) -> None:
        try:
            self._app_data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._runtime_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._runtime_file)
        except Exception:
            pass
        self.changed.emit()

    def _get_last_data_dir(self) -> str:
        v = self._data.get("last_data_dir", "")
        return str(v) if isinstance(v, str) else ""

    def _set_last_data_dir(self, v: str) -> None:
        self._data["last_data_dir"] = (v or "").strip()
        self.save()

    lastDataDir = Property(str, _get_last_data_dir, _set_last_data_dir, notify=changed)

    @Slot()
    def clear(self) -> None:
        self._data = {}
        try:
            if self._runtime_file.exists():
                self._runtime_file.unlink()
        except Exception:
            pass
        self.changed.emit()


def _resolve_onboarding_qml(step: int) -> str:
    mapping = {
        1: "onboarding_1_data_dir.qml",
        2: "onboarding_2_kimi.qml",
        3: "onboarding_3_feishu.qml",
        4: "onboarding_4_naming.qml",
        5: "onboarding_5_quiz.qml",
        6: "onboarding_6_profile_result.qml",
    }
    return mapping.get(int(step), "onboarding_1_data_dir.qml")


def _is_onboarding_in_progress(root: Path) -> bool:
    return (root / ".tmp" / "onboarding_state.json").exists()


def _cleanup_stale_onboarding_tmp(root: Path) -> None:
    tmp_dir = root / ".tmp"
    state_file = tmp_dir / "onboarding_state.json"
    try:
        if state_file.exists():
            state_file.unlink()
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            tmp_dir.rmdir()
    except Exception:
        pass


def _pick_data_dir(runtime: RuntimeStore, root: Path) -> Path:
    last_dir = (runtime.lastDataDir or "").strip()
    if last_dir:
        try:
            p = Path(_normalize_path(last_dir))
            if p.exists():
                return p
        except Exception:
            pass
    return default_user_data_dir(root)


def _current_config_path(runtime: RuntimeStore, root: Path) -> Path:
    return _pick_data_dir(runtime, root) / "config.json"


def _make_blue_tray_icon(size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(QColor(0, 0, 0, 0))
    p.setBrush(QColor("#0A84FF"))
    margin = int(size * 0.12)
    p.drawEllipse(margin, margin, size - 2 * margin, size - 2 * margin)
    p.end()
    return QIcon(pm)


def _load_app_icon(root: Path) -> QIcon:
    for rel in ("assets/app_windows.ico", "assets/app.ico", "assets/app.png"):
        icon_path = root / rel
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            if not icon.isNull():
                return icon
    return _make_blue_tray_icon()


def main() -> int:
    root = _project_root()
    _ensure_sys_path(root)

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtQuickControls2 import QQuickStyle
    QQuickStyle.setStyle("Basic")

    from app.core.onboarding_draft import OnboardingDraft
    from app.services.kimi_client import KimiClient
    from app.services.onboarding_quiz import OnboardingQuiz
    from app.services.profile_generator import ProfileGenerator
    from app.services.onboarding_finalizer import OnboardingFinalizer
    from app.services.feishu_socket import FeishuSocket

    from app.services.window_manager import WindowManager
    from app.services.data_transfer import DataTransfer
    from app.services.settings_service import SettingsService
    from app.services.tray_manager import TrayManager
    from app.services.schedule_service import ScheduleService
    from app.services.memory_graph_service import MemoryGraphService
    from app.services.review_service import ReviewService
    from app.services.chat_service import ChatService
    from app.services.scheduler_service import SchedulerService
    from app.services.global_hotkey_service import GlobalHotkeyService

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    app = QApplication(sys.argv)
    app.setApplicationName("LoosePlan")
    app.setOrganizationName("LoosePlan")
    app.setQuitOnLastWindowClosed(False)

    app_icon = _load_app_icon(root)
    app.setWindowIcon(app_icon)

    app_data_loc = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    app_data_dir = Path(app_data_loc).resolve()
    runtime = RuntimeStore(app_data_dir)

    engine = QQmlApplicationEngine()
    qml_root = root / "qml"
    pages_dir = qml_root / "pages"
    engine.addImportPath(str(qml_root))

    draft = OnboardingDraft(root)
    kimi_client = KimiClient()
    quiz = OnboardingQuiz(root, draft)
    profile_gen = ProfileGenerator(draft, quiz)
    finalizer = OnboardingFinalizer(root, draft)
    feishu_socket = FeishuSocket(root, draft)

    window_mgr = WindowManager(engine=engine, pages_dir=pages_dir)

    def _get_data_dir() -> Path:
        cfgp = _current_config_path(runtime, root)
        if cfgp.exists():
            try:
                cfg = _read_json(cfgp)
                dd = cfg.get("data_dir")
                if isinstance(dd, str) and dd.strip():
                    return Path(dd).expanduser().resolve()
            except Exception:
                pass
        try:
            dd = str(draft.getDraftDataDir() or "").strip()
            if dd:
                return Path(dd).expanduser().resolve()
        except Exception:
            pass
        return cfgp.parent.resolve()

    data_transfer = DataTransfer(get_data_dir=_get_data_dir)
    schedule_service = ScheduleService(get_data_dir=_get_data_dir)
    memory_graph_service = MemoryGraphService(get_data_dir=_get_data_dir)
    review_service = ReviewService(get_data_dir=_get_data_dir)
    chat_service = ChatService(get_data_dir=_get_data_dir, schedule_service=schedule_service)
    scheduler_service = SchedulerService(
        get_data_dir=_get_data_dir,
        schedule_service=schedule_service,
        review_service=review_service,
    )
    hotkey_service = GlobalHotkeyService()
    settings_service = SettingsService(
        project_root=root,
        runtime=runtime,
        get_data_dir=_get_data_dir,
        data_transfer=data_transfer,
        kimi_client=kimi_client,
        feishu_socket=feishu_socket,
    )

    tray_mgr = TrayManager(
        app=app,
        icon=app_icon,
        window_mgr=window_mgr,
        data_transfer=data_transfer,
        runtime=runtime,
        project_root=root,
        draft=draft,
    )

    feishu_socket.setMessageHandler(chat_service.handleFeishuText)

    try:
        feishu_socket.stateChanged.connect(
            lambda s: chat_service.setFeishuConnected(s == feishu_socket.StateConnected)
        )
    except Exception:
        pass
    try:
        scheduler_service.desktopNotify.connect(tray_mgr.showInfo)
        scheduler_service.feishuNotify.connect(feishu_socket.sendToBound)
    except Exception:
        pass
    try:
        review_service.desktopNotify.connect(tray_mgr.showInfo)
        review_service.feishuNotify.connect(feishu_socket.sendToBound)
        review_service.toastRequested.connect(tray_mgr.showInfo)
    except Exception:
        pass
    try:
        hotkey_service.showOrb.connect(tray_mgr.popupMenuAtCursor)
        hotkey_service.openChat.connect(tray_mgr.openChat)
        hotkey_service.openSchedule.connect(tray_mgr.openSchedule)
        hotkey_service.toastRequested.connect(tray_mgr.showInfo)
        app.installNativeEventFilter(hotkey_service)
    except Exception:
        pass
    try:
        settings_service.toastRequested.connect(tray_mgr.showInfo)
    except Exception:
        pass

    ctx = engine.rootContext()
    ctx.setContextProperty("onboardingDraft", draft)
    ctx.setContextProperty("kimiClient", kimi_client)
    ctx.setContextProperty("onboardingQuiz", quiz)
    ctx.setContextProperty("profileGenerator", profile_gen)
    ctx.setContextProperty("onboardingFinalizer", finalizer)
    ctx.setContextProperty("runtimeStore", runtime)
    ctx.setContextProperty("feishuSocket", feishu_socket)
    ctx.setContextProperty("windowManager", window_mgr)
    ctx.setContextProperty("scheduleService", schedule_service)
    ctx.setContextProperty("memoryGraphService", memory_graph_service)
    ctx.setContextProperty("reviewService", review_service)
    ctx.setContextProperty("chatService", chat_service)
    ctx.setContextProperty("settingsService", settings_service)

    host_qml = qml_root / "AppHost.qml"
    if not host_qml.exists():
        host_qml = pages_dir / "onboarding_1_data_dir.qml"  # dev fallback
    engine.load(QUrl.fromLocalFile(str(host_qml)))
    if not engine.rootObjects():
        return 1

    draft.loadDraft()

    # ✅ runtime 自愈：若 runtime.json 未正确记录 last_data_dir，则尝试从 draft 恢复
    try:
        last_dir = (runtime.lastDataDir or "").strip()
    except Exception:
        last_dir = ""

    if not last_dir:
        try:
            dd = str(draft.getDraftDataDir() or "").strip()
        except Exception:
            dd = ""
        if dd:
            try:
                dp = Path(dd).expanduser().resolve()
                if (dp / "config.json").exists():
                    runtime.lastDataDir = str(dp)
            except Exception:
                pass

    step = 1
    try:
        step = int(draft.getDraftStep() or 1)
    except Exception:
        step = 1

    cfg_path = _current_config_path(runtime, root)
    has_cfg = cfg_path.exists()
    onboarding = _is_onboarding_in_progress(root) and not has_cfg

    if has_cfg:
        _cleanup_stale_onboarding_tmp(root)

    if onboarding or not has_cfg:
        qml_name = _resolve_onboarding_qml(step if onboarding else 1)
        window_mgr.open_or_replace(key="onboarding", qml_file=qml_name)
    else:
        window_mgr.open_or_replace(key="chat", qml_file="chat.qml")

        try:
            cfg = _read_json(cfg_path)
            kimi = cfg.get("kimi") if isinstance(cfg.get("kimi"), dict) else {}
            api_key = str(kimi.get("api_key", "") or "")
            base_url = str(kimi.get("base_url", "") or "https://api.moonshot.cn/v1")
            model = str(kimi.get("model", "") or "kimi-k2-thinking-turbo")
            kimi_client.setConfig(api_key, base_url, model)
            try:
                chat_service.setKimiConnected(bool(api_key.strip()))
            except Exception:
                pass
            QTimer.singleShot(50, kimi_client.testCurrent)
        except Exception:
            pass

    try:
        kimi_client.connectedChanged.connect(lambda: chat_service.setKimiConnected(bool(kimi_client.connected)))
    except Exception:
        pass

    try:
        kimi_client.testFinished.connect(lambda ok, _msg: chat_service.setKimiConnected(bool(ok)))
    except Exception:
        pass

    try:
        hotkey_service.start()
    except Exception:
        pass
    QTimer.singleShot(200, scheduler_service.start)
    if not (onboarding or not has_cfg):
        QTimer.singleShot(300, feishu_socket.autoStart)

    def _cleanup_on_quit() -> None:
        try:
            scheduler_service.stop()
        except Exception:
            pass
        try:
            hotkey_service.stop()
        except Exception:
            pass
        try:
            feishu_socket.stopLongConnection()
        except Exception:
            pass

    app.aboutToQuit.connect(_cleanup_on_quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
