from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app.core.app_paths import default_user_data_dir

from .data_transfer import DataTransfer
from .feishu_socket import FeishuSocket
from .kimi_client import KimiClient

try:
    import winreg
except Exception:  # pragma: no cover - non-Windows fallback
    winreg = None


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if default is None:
        default = {}
    try:
        if path.exists():
            obj = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                return obj
    except Exception:
        pass
    return dict(default)


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _default_config(data_dir: Path) -> dict[str, Any]:
    return {
        "data_dir": str(data_dir),
        "user_display_name": "",
        "assistant_name": "",
        "kimi": {
            "api_key": "",
            "base_url": "https://api.moonshot.cn/v1",
            "model": "kimi-k2-thinking-turbo",
        },
        "feishu": {
            "enabled": False,
            "app_id": "",
            "app_secret": "",
            "bound_receive_id": "",
            "bound_receive_type": "chat_id",
            "last_connected_at": "",
        },
        "push": {
            "weekly_review": {"enabled": True, "weekday": 0, "sync_feishu": True},
            "schedule_reminder": {"enabled": True, "default_remind_before_min": 10},
        },
        "runtime": {
            "last_daily_refresh_date": "",
            "last_weekly_review_key": "",
        },
    }


def _merge_dict(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge_dict(dst[key], value)
        else:
            dst[key] = value
    return dst


def _is_subpath(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


class SettingsService(QObject):
    changed = Signal()
    toastRequested = Signal(str)

    def __init__(
        self,
        *,
        project_root: Path,
        runtime: QObject,
        get_data_dir: Callable[[], Path],
        data_transfer: DataTransfer,
        kimi_client: KimiClient,
        feishu_socket: FeishuSocket,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._project_root = Path(project_root).resolve()
        self._runtime = runtime
        self._get_data_dir = get_data_dir
        self._data_transfer = data_transfer
        self._kimi_client = kimi_client
        self._feishu_socket = feishu_socket
        self._cfg: dict[str, Any] = {}
        self._autostart_enabled = False

        try:
            self._data_transfer.toastRequested.connect(self.toastRequested.emit)
        except Exception:
            pass

        self.reload()

    def _emit_toast(self, text: str) -> None:
        msg = (text or "").strip()
        if msg:
            self.toastRequested.emit(msg)

    def _current_data_dir(self) -> Path:
        try:
            return self._get_data_dir().expanduser().resolve()
        except Exception:
            return default_user_data_dir(self._project_root)

    def _config_path(self) -> Path:
        return self._current_data_dir() / "config.json"

    def _load_config(self) -> dict[str, Any]:
        data_dir = self._current_data_dir()
        cfg = _default_config(data_dir)
        disk = _read_json(self._config_path(), {})
        _merge_dict(cfg, disk)
        cfg["data_dir"] = str(data_dir)
        return cfg

    def _save_config(self, cfg: dict[str, Any]) -> None:
        data_dir = self._current_data_dir()
        cfg["data_dir"] = str(data_dir)
        _atomic_write_json(data_dir / "config.json", cfg)
        self._cfg = cfg
        self.changed.emit()

    def _reload_autostart(self) -> None:
        self._autostart_enabled = self._read_autostart_enabled()

    def _runtime_last_data_dir(self) -> str:
        try:
            return str(getattr(self._runtime, "lastDataDir") or "").strip()
        except Exception:
            return ""

    def _set_runtime_last_data_dir(self, path: Path) -> None:
        try:
            setattr(self._runtime, "lastDataDir", str(path.expanduser().resolve()))
        except Exception:
            pass

    def _get_kimi(self) -> dict[str, Any]:
        kimi = self._cfg.get("kimi")
        return kimi if isinstance(kimi, dict) else {}

    def _get_feishu(self) -> dict[str, Any]:
        feishu = self._cfg.get("feishu")
        return feishu if isinstance(feishu, dict) else {}

    def _get_push(self) -> dict[str, Any]:
        push = self._cfg.get("push")
        return push if isinstance(push, dict) else {}

    def _get_weekly(self) -> dict[str, Any]:
        weekly = self._get_push().get("weekly_review")
        return weekly if isinstance(weekly, dict) else {}

    def _get_reminder(self) -> dict[str, Any]:
        reminder = self._get_push().get("schedule_reminder")
        return reminder if isinstance(reminder, dict) else {}

    def _read_autostart_enabled(self) -> bool:
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                value, _ = winreg.QueryValueEx(key, "LoosePlan")
            return bool(str(value or "").strip())
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _autostart_command(self) -> str:
        if getattr(sys, "frozen", False):
            return f'"{Path(sys.executable).resolve()}"'

        python_bin = Path(sys.executable).resolve()
        pythonw_bin = python_bin.with_name("pythonw.exe")
        if pythonw_bin.exists():
            python_bin = pythonw_bin

        main_py = (self._project_root / "app" / "main.py").resolve()
        return f'"{python_bin}" "{main_py}"'

    @Property(str, notify=changed)
    def dataDir(self) -> str:
        return str(self._cfg.get("data_dir", "") or "")

    @Property(str, notify=changed)
    def kimiApiKey(self) -> str:
        return str(self._get_kimi().get("api_key", "") or "")

    @Property(str, notify=changed)
    def kimiBaseUrl(self) -> str:
        return str(self._get_kimi().get("base_url", "") or "https://api.moonshot.cn/v1")

    @Property(str, notify=changed)
    def kimiModel(self) -> str:
        return str(self._get_kimi().get("model", "") or "kimi-k2-thinking-turbo")

    @Property(str, notify=changed)
    def feishuAppId(self) -> str:
        return str(self._get_feishu().get("app_id", "") or "")

    @Property(str, notify=changed)
    def feishuAppSecret(self) -> str:
        return str(self._get_feishu().get("app_secret", "") or "")

    @Property(str, notify=changed)
    def feishuBoundReceiveId(self) -> str:
        return str(self._get_feishu().get("bound_receive_id", "") or "")

    @Property(int, notify=changed)
    def weeklyReviewWeekday(self) -> int:
        try:
            return max(0, min(int(self._get_weekly().get("weekday", 0) or 0), 6))
        except Exception:
            return 0

    @Property(bool, notify=changed)
    def weeklyReviewSyncFeishu(self) -> bool:
        return bool(self._get_weekly().get("sync_feishu", True))

    @Property(int, notify=changed)
    def defaultRemindBeforeMin(self) -> int:
        try:
            return max(0, min(int(self._get_reminder().get("default_remind_before_min", 10) or 10), 60))
        except Exception:
            return 10

    @Property(bool, notify=changed)
    def autoStartEnabled(self) -> bool:
        return bool(self._autostart_enabled)

    @Slot()
    def reload(self) -> None:
        self._cfg = self._load_config()
        self._reload_autostart()
        self.changed.emit()

    @Slot(str, str, str)
    def saveKimi(self, api_key: str, base_url: str, model: str) -> None:
        cfg = self._load_config()
        kimi = cfg.get("kimi")
        if not isinstance(kimi, dict):
            kimi = {}
            cfg["kimi"] = kimi
        kimi["api_key"] = (api_key or "").strip()
        kimi["base_url"] = (base_url or "").strip() or "https://api.moonshot.cn/v1"
        kimi["model"] = (model or "").strip() or "kimi-k2-thinking-turbo"
        self._save_config(cfg)
        try:
            self._kimi_client.setConfig(kimi["api_key"], kimi["base_url"], kimi["model"])
            self._kimi_client.resetStatus()
        except Exception:
            pass

    @Slot(str, str)
    def saveFeishu(self, app_id: str, app_secret: str) -> None:
        cfg = self._load_config()
        feishu = cfg.get("feishu")
        if not isinstance(feishu, dict):
            feishu = {}
            cfg["feishu"] = feishu
        feishu["app_id"] = (app_id or "").strip()
        feishu["app_secret"] = (app_secret or "").strip()
        feishu["enabled"] = bool(feishu["app_id"] and feishu["app_secret"])
        feishu.setdefault("bound_receive_id", "")
        feishu.setdefault("bound_receive_type", "chat_id")
        feishu.setdefault("last_connected_at", "")
        self._save_config(cfg)

    @Slot(int, bool, int)
    def savePush(self, weekday: int, sync_feishu: bool, remind_before_min: int) -> None:
        cfg = self._load_config()
        push = cfg.get("push")
        if not isinstance(push, dict):
            push = {}
            cfg["push"] = push
        weekly = push.get("weekly_review")
        if not isinstance(weekly, dict):
            weekly = {}
            push["weekly_review"] = weekly
        reminder = push.get("schedule_reminder")
        if not isinstance(reminder, dict):
            reminder = {}
            push["schedule_reminder"] = reminder

        weekly["enabled"] = bool(weekly.get("enabled", True))
        weekly["weekday"] = max(0, min(int(weekday), 6))
        weekly["sync_feishu"] = bool(sync_feishu)

        reminder["enabled"] = bool(reminder.get("enabled", True))
        reminder["default_remind_before_min"] = max(0, min(int(remind_before_min), 60))
        self._save_config(cfg)

    @Slot(bool)
    def setAutoStartEnabled(self, enabled: bool) -> None:
        if winreg is None:
            self._emit_toast("当前环境不支持开机自启设置")
            return
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                if enabled:
                    winreg.SetValueEx(key, "LoosePlan", 0, winreg.REG_SZ, self._autostart_command())
                else:
                    try:
                        winreg.DeleteValue(key, "LoosePlan")
                    except FileNotFoundError:
                        pass
        except Exception as ex:
            self._emit_toast(f"设置开机自启失败：{ex}")
            self._reload_autostart()
            self.changed.emit()
            return

        self._reload_autostart()
        self.changed.emit()
        self._emit_toast("已更新开机自启设置")

    def _copy_data_tree(self, src: Path, dst: Path) -> None:
        dst.mkdir(parents=True, exist_ok=True)
        if not src.exists():
            return
        for child in src.iterdir():
            target = dst / child.name
            if child.is_dir():
                shutil.copytree(child, target, dirs_exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)

    @Slot()
    def chooseAndMoveDataDir(self) -> None:
        current_dir = self._current_data_dir()
        start_dir = current_dir.parent if current_dir.exists() else current_dir
        chosen = QFileDialog.getExistingDirectory(None, "选择新的数据目录", str(start_dir))
        if not chosen:
            return

        target_dir = Path(chosen).expanduser().resolve()
        if target_dir == current_dir:
            self._emit_toast("当前已在该数据目录")
            return
        if _is_subpath(target_dir, current_dir):
            self._emit_toast("新的数据目录不能位于当前数据目录内部")
            return

        answer = QMessageBox.question(
            None,
            "更改数据目录",
            f"将把当前数据复制到新目录：\n{target_dir}\n\n原目录会保留作为备份。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self._copy_data_tree(current_dir, target_dir)
            cfg = _read_json(current_dir / "config.json", _default_config(target_dir))
            cfg["data_dir"] = str(target_dir)
            _atomic_write_json(target_dir / "config.json", cfg)
            self._set_runtime_last_data_dir(target_dir)
            self.reload()

            try:
                self._kimi_client.setConfig(self.kimiApiKey, self.kimiBaseUrl, self.kimiModel)
                self._kimi_client.resetStatus()
            except Exception:
                pass

            try:
                self._feishu_socket.stopLongConnection()
                self._feishu_socket.autoStart()
            except Exception:
                pass

            self._emit_toast("数据目录已更新")
        except Exception as ex:
            self._emit_toast(f"迁移数据目录失败：{ex}")

    @Slot()
    def exportData(self) -> None:
        try:
            self._data_transfer.exportZip(False)
        except Exception as ex:
            self._emit_toast(f"导出失败：{ex}")

    @Slot()
    def importData(self) -> None:
        try:
            self._data_transfer.importZip()
        except Exception as ex:
            self._emit_toast(f"导入失败：{ex}")
