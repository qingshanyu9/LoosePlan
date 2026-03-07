# app/services/data_transfer.py
from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox


class DataTransfer(QObject):
    toastRequested = Signal(str)

    def __init__(self, *, get_data_dir: Callable[[], Path], parent: QObject | None = None):
        super().__init__(parent)
        self._get_data_dir = get_data_dir

    def _toast(self, text: str) -> None:
        message = (text or "").strip()
        if message:
            self.toastRequested.emit(message)

    def _sanitized_config_text(self, path: Path) -> str:
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj, dict):
                raise ValueError("config.json is not an object")
            kimi = obj.get("kimi")
            if isinstance(kimi, dict):
                kimi["api_key"] = ""
            feishu = obj.get("feishu")
            if isinstance(feishu, dict):
                feishu["app_secret"] = ""
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            return path.read_text(encoding="utf-8")

    @Slot()
    def export_zip(self) -> None:
        self.exportZip(False)

    @Slot(bool)
    def exportZip(self, include_secrets: bool = False) -> None:
        data_dir = self._get_data_dir()
        if not data_dir.exists():
            self._toast("数据目录不存在")
            return

        default_name = f"LoosePlan_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        out_path, _ = QFileDialog.getSaveFileName(
            None,
            "导出数据",
            str((data_dir.parent / default_name).resolve()),
            "ZIP (*.zip)",
        )
        if not out_path:
            return

        out = Path(out_path).resolve()
        try:
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for path in data_dir.rglob("*"):
                    if path.is_dir():
                        continue
                    rel = str(path.relative_to(data_dir)).replace("\\", "/")
                    if rel == "config.json" and not include_secrets:
                        zf.writestr(rel, self._sanitized_config_text(path))
                    else:
                        zf.write(path, arcname=rel)
            self._toast("导出完成")
        except Exception as ex:
            self._toast(f"导出失败：{ex}")

    @Slot()
    def import_zip(self) -> None:
        self.importZip()

    @Slot()
    def importZip(self) -> None:
        data_dir = self._get_data_dir()
        zip_path, _ = QFileDialog.getOpenFileName(None, "导入数据", str(data_dir.parent), "ZIP (*.zip)")
        if not zip_path:
            return

        zipf = Path(zip_path).resolve()
        if not zipf.exists():
            self._toast("ZIP 文件不存在")
            return

        ret = QMessageBox.question(
            None,
            "导入确认",
            f"将把 {zipf.name} 解压覆盖到当前数据目录：\n{data_dir}\n\n建议先导出备份。继续吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            if any(data_dir.iterdir()):
                backup_dir = data_dir.with_name(data_dir.name + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                try:
                    shutil.copytree(data_dir, backup_dir)
                except Exception:
                    pass

            with zipfile.ZipFile(zipf, "r") as zf:
                zf.extractall(data_dir)

            self._toast("导入完成：请重启 LoosePlan 以重新加载配置")
        except Exception as ex:
            self._toast(f"导入失败：{ex}")
