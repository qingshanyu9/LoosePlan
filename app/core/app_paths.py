from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths


def app_state_dir(project_root: Path | None = None) -> Path:
    location = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if location:
        return Path(location).expanduser().resolve()

    if project_root is not None:
        return (Path(project_root).resolve() / ".appdata").resolve()

    return (Path.home().resolve() / ".looseplan").resolve()


def default_user_data_dir(project_root: Path | None = None) -> Path:
    if not getattr(sys, "frozen", False) and project_root is not None:
        return (Path(project_root).resolve() / "data").resolve()

    return (app_state_dir(project_root) / "data").resolve()
