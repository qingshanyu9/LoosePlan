from __future__ import annotations

import os
import sys
from pathlib import Path


def _project_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[1]


def _prepare_dll_search_path(root: Path) -> None:
    candidates = [
        root,
        root / "PySide6",
        root / "shiboken6",
    ]

    path_parts: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        path_parts.append(str(candidate))
        try:
            os.add_dll_directory(str(candidate))
        except (AttributeError, FileNotFoundError, OSError):
            pass

    if not path_parts:
        return

    existing = os.environ.get("PATH", "")
    prefix = os.pathsep.join(path_parts)
    if existing:
        os.environ["PATH"] = prefix + os.pathsep + existing
    else:
        os.environ["PATH"] = prefix


def main() -> int:
    root = _project_root()
    _prepare_dll_search_path(root)

    from app.main import main as app_main

    return app_main()


if __name__ == "__main__":
    raise SystemExit(main())
